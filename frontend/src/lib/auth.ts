// Access key for using the app from another device (the iPhone). The Mac itself
// never needs it. Stored only in this browser.

export const ACCESS_KEY_HEADER = "X-Access-Key";
const STORAGE_KEY = "fin_tracker.access_key";

/** Thrown when the API answers 401: the access key is missing or wrong. */
export class AuthRequiredError extends Error {
  constructor() {
    super("Se necesita la clave de acceso");
    this.name = "AuthRequiredError";
  }
}

export function getAccessKey(storage: Pick<Storage, "getItem"> | undefined): string | null {
  try {
    return storage?.getItem(STORAGE_KEY) ?? null;
  } catch {
    return null;
  }
}

export function saveAccessKey(storage: Pick<Storage, "setItem"> | undefined, accessKey: string): void {
  try {
    storage?.setItem(STORAGE_KEY, accessKey.trim());
  } catch {
    // Without storage the key is just asked again next time
  }
}

/** Header carrying the access key, or nothing when there is none. */
export function buildAuthHeaders(accessKey: string | null): Record<string, string> {
  return accessKey ? { [ACCESS_KEY_HEADER]: accessKey } : {};
}

export function getBrowserStorage(): Storage | undefined {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}
