class LocalStorageServiceClass {
    get(key) {
        const raw = localStorage.getItem(key);
        if (raw === null)
            return null;
        try {
            return JSON.parse(raw);
        }
        catch {
            return null;
        }
    }
    set(key, value) {
        localStorage.setItem(key, JSON.stringify(value));
    }
    remove(key) {
        localStorage.removeItem(key);
    }
    clear() {
        localStorage.clear();
    }
}
export const LocalStorageService = new LocalStorageServiceClass();
