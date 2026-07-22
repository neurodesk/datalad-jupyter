"use strict";
function getCookie(name) {
    var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
    return r ? r[1] : undefined;
}
class Dataset {
    constructor(base_url) {
        this.url = base_url + 'dataset';
        this._xsrf = getCookie("_xsrf");
        this._head_auth = {
            'X-XSRFToken': this._xsrf,
        };
        this._head_auth_json = {
            'Content-Type': 'application/json',
            'X-XSRFToken': this._xsrf,
        };
    }
    async search(query, page = 1, per_page = 20) {
        let url = this.url + '/search?page=' + page + '&per_page=' + per_page;
        if (query) {
            url += '&q=' + encodeURIComponent(query);
        }
        const response = await fetch(url, { headers: this._head_auth });
        if (response.ok) {
            return response.json();
        }
        throw new Error('Search failed: ' + response.status);
    }
    async listCloned() {
        const response = await fetch(this.url, { headers: this._head_auth });
        if (response.ok) {
            return response.json();
        }
        return [];
    }
    async clone(datasetUrl) {
        const response = await fetch(this.url + '/clone', {
            method: 'POST',
            headers: this._head_auth_json,
            body: JSON.stringify({ url: datasetUrl }),
        });
        return response.json();
    }
    async cloneStatus(cloneId) {
        const response = await fetch(this.url + '/clone/' + cloneId, { headers: this._head_auth });
        if (response.ok) {
            return response.json();
        }
        return null;
    }
    async config() {
        const response = await fetch(this.url + '/config', { headers: this._head_auth });
        if (response.ok) {
            return response.json();
        }
        return null;
    }
    async show(name) {
        const response = await fetch(this.url + '/show/' + encodeURIComponent(name), { headers: this._head_auth });
        if (response.ok) {
            return response.json();
        }
        return null;
    }
    async metadata(datasetUrl) {
        const response = await fetch(this.url + '/metadata?url=' + encodeURIComponent(datasetUrl), { headers: this._head_auth });
        if (response.ok) {
            return response.json();
        }
        return null;
    }
}
// AMD export for classic notebook
if (typeof define === 'function') {
    define({
        Dataset: Dataset
    });
}
// CommonJS export for TypeScript/JupyterLab
try {
    exports.Dataset = Dataset;
}
catch (e) { }
