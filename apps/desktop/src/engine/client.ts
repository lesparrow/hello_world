import { invoke, isTauri } from '@tauri-apps/api/core';
import type { EngineMethods, MethodName } from './types';

/** Erreur renvoyée par le moteur, avec un message destiné à l'utilisateur. */
export class EngineError extends Error {
  constructor(
    message: string,
    public readonly code: number,
    public readonly kind: string | undefined,
  ) {
    super(message);
    this.name = 'EngineError';
  }
}

interface RpcResponse {
  jsonrpc: '2.0';
  id: number;
  result?: unknown;
  error?: { code: number; message: string; data?: { kind?: string } };
}

let nextId = 1;

export const runningInTauri = (): boolean => isTauri();

async function send(payload: string): Promise<RpcResponse> {
  if (runningInTauri()) {
    // La coquille Tauri relaie le message au moteur Python par stdin/stdout.
    const raw = await invoke<string>('engine_call', { payload });
    return JSON.parse(raw) as RpcResponse;
  }
  if (import.meta.env.DEV) {
    const res = await fetch('/rpc', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
    });
    if (!res.ok) throw new EngineError('Le moteur de développement est injoignable.', -1, 'transport');
    return (await res.json()) as RpcResponse;
  }
  throw new EngineError("Le moteur de calcul n'est pas disponible.", -1, 'transport');
}

export async function call<M extends MethodName>(
  method: M,
  params?: EngineMethods[M]['params'],
): Promise<EngineMethods[M]['result']> {
  const id = nextId++;
  let response: RpcResponse;
  try {
    response = await send(JSON.stringify({ jsonrpc: '2.0', id, method, params: params ?? {} }));
  } catch (err) {
    if (err instanceof EngineError) throw err;
    throw new EngineError(
      `Communication impossible avec le moteur de calcul : ${String(err)}`,
      -1,
      'transport',
    );
  }
  if (response.error) {
    throw new EngineError(response.error.message, response.error.code, response.error.data?.kind);
  }
  return response.result as EngineMethods[M]['result'];
}

export function errorMessage(err: unknown): string {
  if (err instanceof EngineError) return err.message;
  if (err instanceof Error) return err.message;
  return String(err);
}
