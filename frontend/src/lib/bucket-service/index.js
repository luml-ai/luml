import axios from 'axios';
export class ModelDownloader {
    url;
    constructor(url) {
        this.url = url;
    }
    async getFileFromBucket(fileIndex, fileName, buffer, outerOffset = 0, signal) {
        const range = this.getRangeHeader(fileIndex, fileName, outerOffset);
        const file = await axios.get(this.url, {
            headers: { Range: range },
            responseType: buffer ? 'arraybuffer' : 'json',
            signal,
        });
        return file.data;
    }
    getRangeHeader(fileIndex, fileName, outerOffset = 0) {
        const range = fileIndex[fileName];
        if (!range)
            throw new Error('Model not include this file');
        const start = range[0] + outerOffset;
        const end = start + range[1] - 1;
        return `bytes=${start}-${end}`;
    }
}
