/**
 * Passkey authentication utilities
 * Base62 encoding/decoding and validation logic
 */

const B62 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

function b62Encode(data: Uint8Array): string {
  let n = 0n;
  for (const byte of data) {
    n = (n << 8n) | BigInt(byte);
  }
  
  if (n === 0n) {
    return B62[0];
  }
  
  const result: string[] = [];
  while (n > 0n) {
    result.push(B62[Number(n % 62n)]);
    n = n / 62n;
  }
  
  return result.reverse().join("");
}

function b62Decode(s: string): Uint8Array | null {
  try {
    let n = 0n;
    for (const ch of s) {
      const idx = B62.indexOf(ch);
      if (idx === -1) return null;
      n = n * 62n + BigInt(idx);
    }
    
    if (n === 0n) {
      return new Uint8Array([0]);
    }
    
    const bytes: number[] = [];
    while (n > 0n) {
      bytes.unshift(Number(n & 0xFFn));
      n = n >> 8n;
    }
    
    return new Uint8Array(bytes);
  } catch {
    return null;
  }
}

function encode(raw: string): string {
  const encoder = new TextEncoder();
  return b62Encode(encoder.encode(raw));
}

function decode(token: string): string | null {
  try {
    const bytes = b62Decode(token);
    if (!bytes) return null;
    const decoder = new TextDecoder();
    return decoder.decode(bytes);
  } catch {
    return null;
  }
}

export interface PasskeyValidationResult {
  valid: boolean;
  message: string;
}

export async function validatePasskey(passkey: string, apiUrl: string): Promise<PasskeyValidationResult> {
  try {
    const response = await fetch(`${apiUrl}/passkey/validate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ passkey: passkey.trim() }),
    });
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Validation failed" }));
      return {
        valid: false,
        message: error.detail || "Validation failed",
      };
    }
    
    const result = await response.json();
    return result;
  } catch (error) {
    console.error("Passkey validation error:", error);
    return {
      valid: false,
      message: "Unable to connect to authentication server. Please try again.",
    };
  }
}

export function isAuthenticated(): boolean {
  return sessionStorage.getItem("authenticated") === "true";
}

export function setAuthenticated(value: boolean): void {
  if (value) {
    sessionStorage.setItem("authenticated", "true");
  } else {
    sessionStorage.removeItem("authenticated");
  }
}

export function clearAuthentication(): void {
  sessionStorage.removeItem("authenticated");
}
