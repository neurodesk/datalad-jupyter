import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin,
  ILayoutRestorer,
} from "@jupyterlab/application";

import { Dialog, showDialog, ICommandPalette } from "@jupyterlab/apputils";

import { Widget } from "@lumino/widgets";

import { PageConfig } from "@jupyterlab/coreutils";

import { Dataset } from "../datalad_jupyter/static/dataset.js";

import { LabIcon } from "@jupyterlab/ui-components";

function datasetNameFromUrl(url: string): string {
  let name = url.replace(/\/+$/, "").split("/").pop() || url;
  if (name.endsWith(".git")) {
    name = name.slice(0, -4);
  }
  return name;
}

import dataladIconSvg from "./assets/data.svg";
export const jpdataladIcon = new LabIcon({
  name: "jupyter_datalad:datalad_logo",
  svgstr: dataladIconSvg,
});

const datasetAPI = new Dataset(PageConfig.getBaseUrl());

function createDatasetItem(label: string, ...buttons: string[]) {
  const item = document.createElement("li");
  const itemLabel = document.createElement("span");
  item.append(itemLabel);
  item.setAttribute("class", "jp-Dataset-item");
  itemLabel.setAttribute("class", "jp-Dataset-itemLabel");
  itemLabel.innerText = label;
  for (const btn of buttons) {
    const itemButton = document.createElement("button");
    itemButton.setAttribute("class", "jp-Dataset-itemButton jp-mod-styled");
    itemButton.innerHTML = btn;
    item.append(itemButton);
  }
  return item;
}

async function show_dataset(name) {
  const data = await datasetAPI.show(name);
  if (data) {
    let text = "Path: " + data.path;
    if (data.url) text += "\nURL: " + data.url;
    if (data.ds_id) text += "\nDataset ID: " + data.ds_id;
    showDialog({
      title: name,
      body: new DatasetDialogWidget("Dataset Info", text),
      buttons: [Dialog.okButton()],
    });
  }
}

async function clone_dataset(url) {
  const result = await datasetAPI.clone(url);
  if (result.error) {
    showDialog({
      title: "Clone Error",
      body: new DatasetDialogWidget("Error", result.error),
      buttons: [Dialog.okButton()],
    });
    return;
  }

  // Poll for completion (timeout after 10 minutes)
  const cloneId = result.clone_id;
  const pollStart = Date.now();
  const pollTimeout = 10 * 60 * 1000;
  await new Promise<void>((resolve) => {
    const pollInterval = setInterval(async () => {
      if (Date.now() - pollStart > pollTimeout) {
        clearInterval(pollInterval);
        showDialog({
          title: "Clone Timeout",
          body: new DatasetDialogWidget(
            "Timeout",
            "Clone polling timed out after 10 minutes. The clone may still be running on the server.",
          ),
          buttons: [Dialog.okButton()],
        });
        resolve();
        return;
      }
      const status = await datasetAPI.cloneStatus(cloneId);
      if (!status) {
        clearInterval(pollInterval);
        resolve();
        return;
      }
      if (status.status === "completed") {
        clearInterval(pollInterval);
        showDialog({
          title: "Clone Complete",
          body: new DatasetDialogWidget(
            "Success",
            "Dataset cloned to: " + status.path,
          ),
          buttons: [Dialog.okButton()],
        });
        resolve();
      } else if (status.status === "failed") {
        clearInterval(pollInterval);
        showDialog({
          title: "Clone Failed",
          body: new DatasetDialogWidget("Error", status.error || "Unknown error"),
          buttons: [Dialog.okButton()],
        });
        resolve();
      }
    }, 2000);
  });
}

/**
 * Main widget for browsing and managing DataLad datasets.
 */
class DatasetWidget extends Widget {
  protected clonedUList: HTMLUListElement;
  protected availUList: HTMLUListElement;
  protected availContainer: HTMLDivElement;
  protected availHeader: HTMLHeadingElement;
  protected searchInput: HTMLInputElement;
  protected searchTimeout: any;
  protected currentPage: number;
  protected totalCount: number;
  protected loadedCount: number;
  protected isLoadingMore: boolean;
  protected currentQuery: string | null;

  constructor() {
    super();

    this.id = "dataset-jupyterlab";
    this.title.caption = "DataLad Datasets";
    this.title.icon = jpdataladIcon;
    this.addClass("jp-Dataset");

    const search_div = document.createElement("div");
    const search_div_wrapper = document.createElement("div");
    this.searchInput = document.createElement("input");
    search_div.setAttribute("class", "jp-Dataset-search");
    search_div_wrapper.setAttribute("class", "jp-Dataset-search-wrapper");
    this.searchInput.setAttribute("id", "datasets");
    this.searchInput.setAttribute("class", "jp-Dataset-input");
    this.searchInput.setAttribute(
      "placeholder",
      "Search datasets in registry...",
    );
    search_div.appendChild(search_div_wrapper);
    search_div_wrapper.appendChild(this.searchInput);
    this.node.insertAdjacentElement("afterbegin", search_div);

    this.node.insertAdjacentHTML(
      "beforeend",
      `<div id="dataset" class="jp-Dataset-content">
          <div class="jp-Dataset-section">
              <div class="jp-Dataset-sectionHeader"><H2>Cloned Datasets</H2></div>
              <div class="jp-Dataset-sectionContainer">
                  <ul class="jp-Dataset-sectionList" id="dataset_cloned_list">
                  </ul>
              </div>
          </div>
          <div class="jp-Dataset-section">
              <div class="jp-Dataset-sectionHeader">
                <h2 id="dataset_avail_header">Available Datasets</h2>
              </div>
              <div class="jp-Dataset-sectionContainer">
                <ul class="jp-Dataset-sectionList" id="dataset_avail_list">
                </ul>
              </div>
          </div>
      </div>`,
    );

    this.clonedUList = this.node.querySelector("#dataset_cloned_list");
    this.availUList = this.node.querySelector("#dataset_avail_list");
    this.availContainer = this.node.querySelector("#dataset") as HTMLDivElement;
    this.availHeader = this.node.querySelector("#dataset_avail_header");

    this.currentPage = 1;
    this.totalCount = 0;
    this.loadedCount = 0;
    this.isLoadingMore = false;
    this.currentQuery = null;

    this.clonedUList.addEventListener("click", this.onClickCloned.bind(this));
    this.availUList.addEventListener("click", this.onClickAvail.bind(this));

    // Debounced search
    this.searchInput.addEventListener("keyup", () => {
      clearTimeout(this.searchTimeout);
      this.searchTimeout = setTimeout(() => this.doSearch(), 400);
    });

    // Infinite scroll on available datasets container
    this.availContainer.addEventListener("scroll", () => {
      const el = this.availContainer;
      if (el.scrollTop + el.clientHeight >= el.scrollHeight - 50) {
        this.loadMore();
      }
    });
  }

  protected async onClickCloned(event) {
    const target = event.target;
    if (target.tagName === "SPAN") {
      show_dataset(target.innerText);
    }
  }

  protected async onClickAvail(event) {
    const target = event.target;
    if (target.tagName === "BUTTON") {
      const parent_li = target.closest("li");
      const urlSpan = parent_li.querySelector("span");
      const url = urlSpan.getAttribute("data-url");
      if (target.innerText === "Info" && url) {
        const name = urlSpan.innerText;
        let text = "URL: " + url;
        const result = await datasetAPI.metadata(url);
        if (result && result.url_metadata) {
          for (const entry of result.url_metadata) {
            const meta = entry.extracted_metadata || {};
            if (meta.Name) text += "\nName: " + meta.Name;
            if (meta.Description) text += "\nDescription: " + meta.Description;
            if (meta.License) text += "\nLicense: " + meta.License;
            if (meta.Author) text += "\nAuthor: " + JSON.stringify(meta.Author);
            if (meta.Keywords) text += "\nKeywords: " + meta.Keywords.join(", ");
            if (entry.metadata_id) text += "\nMetadata ID: " + entry.metadata_id;
          }
        }
        showDialog({
          title: name,
          body: new DatasetDialogWidget("Dataset Info", text),
          buttons: [Dialog.okButton()],
        });
      } else if (url && target.innerText === "Clone") {
        target.innerText = "Cloning...";
        target.style.backgroundColor = "#99b644";
        parent_li.style.backgroundColor = "#dde6c0";
        await clone_dataset(url);
        this.updateCloned();
      }
    }
  }

  public update() {
    this.updateCloned();
    this.doSearch();
  }

  protected async updateCloned() {
    const datasets = await datasetAPI.listCloned();
    this.clonedUList.innerText = "";
    const items = datasets.map((ds) => {
      const item = createDatasetItem(ds.name, "Info");
      return item;
    });
    this.clonedUList.append(...items);
  }

  protected async doSearch() {
    this.currentQuery = this.searchInput.value || null;
    this.currentPage = 1;
    this.loadedCount = 0;
    this.totalCount = 0;
    this.availUList.innerText = "";
    await this.fetchPage();
  }

  protected async loadMore() {
    if (this.isLoadingMore || this.loadedCount >= this.totalCount) {
      return;
    }
    this.currentPage++;
    await this.fetchPage();
  }

  protected async fetchPage() {
    this.isLoadingMore = true;
    try {
      const result = await datasetAPI.search(this.currentQuery, this.currentPage);
      const datasets = result.dataset_urls || [];
      const items = datasets.map((ds) => {
        const url = ds.url || "";
        const name = ds.extracted_metadata?.Name || datasetNameFromUrl(url);
        const item = createDatasetItem(name, "Info", "Clone");
        const span = item.querySelector("span");
        span.setAttribute("data-url", url);
        span.setAttribute("title", url);
        return item;
      });
      this.availUList.append(...items);

      this.totalCount =
        result.collection_stats?.summary?.ds_count || datasets.length;
      this.loadedCount += datasets.length;
      this.availHeader.innerText = `Available Datasets (${this.loadedCount} of ${this.totalCount})`;
    } catch (e) {
      this.availHeader.innerText = "Available Datasets (error loading)";
    }
    this.isLoadingMore = false;
  }
}

/**
 * Activate the dataset widget extension.
 */
async function activate(
  app: JupyterFrontEnd,
  palette: ICommandPalette,
  restorer: ILayoutRestorer,
) {
  const widget = new DatasetWidget();
  restorer.add(widget, "dataset-sessions");
  app.shell.add(widget, "left", { rank: 1000 });
  widget.update();
  console.log("JupyterFrontEnd extension datalad is activated!");
}

const extension: JupyterFrontEndPlugin<void> = {
  id: "jupyterlab_datalad",
  autoStart: true,
  requires: [ICommandPalette, ILayoutRestorer],
  activate: activate,
};

class DatasetDialogWidget extends Widget {
  constructor(labelText, content) {
    let body = document.createElement("div");

    let label = document.createElement("label");
    label.innerHTML = labelText;
    body.appendChild(label);

    let div = document.createElement("div");
    div.classList.add("jp-JSONEditor-host");
    div.setAttribute("style", "min-height:inherit;");
    let text = document.createElement("pre");
    text.setAttribute("style", "margin:10px 10px; white-space:pre-wrap;");
    text.innerText = content;
    div.appendChild(text);
    body.appendChild(div);

    super({ node: body });
  }
}

export default extension;
