/* eslint-disable @typescript-eslint/no-explicit-any */
import { JobService } from "windmill-client";
import { Preview } from "windmill-client";
import { ScriptService } from "windmill-client";

declare global {
  // eslint-disable-next-line no-var
  var windmill:
    | {
        workspace: string | undefined;
        email: string | undefined;
        username: string | undefined;
        token: string | undefined;
      }
    | undefined;
}

export const workspace: string =
  globalThis.windmill?.workspace ?? import.meta.env.VITE_WORKSPACE;
export const email: string =
  globalThis.windmill?.email ?? import.meta.env.VITE_EMAIL;
export const username: string =
  globalThis.windmill?.username ?? import.meta.env.VITE_USERNAME;
export const token: string | undefined =
  globalThis.windmill?.token ?? import.meta.env.VITE_TOKEN;

export function getUser() {
  return import.meta.env.USER;
}

export async function executeInlineScript(
  language: Preview.language,
  content: string,
  args: any
): Promise<any> {
  const uuid = await JobService.runScriptPreview({
    workspace: workspace,
    requestBody: {
      content,
      args,
      language,
    },
  });
  return getResult(uuid);
}

export async function executeWorkspaceScript(
  path: string,
  args: any
): Promise<any> {
  const uuid = await JobService.runScriptByHash({
    workspace: workspace,
    hash: await resolveScriptHash(path),
    requestBody: args,
  });
  return getResult(uuid);
}

export async function executeWorkspaceFlow(
  path: string,
  args: any
): Promise<any> {
  const uuid = await JobService.runFlowByPath({
    workspace: workspace,
    path,
    requestBody: args,
  });
  return getResult(uuid);
}

const scriptHashCache = new Map<string, string>();

async function resolveScriptHash(path: string): Promise<string> {
  const cached = scriptHashCache.get(path);
  if (cached) return cached;
  const script = await ScriptService.getScriptByPath({ workspace, path });
  scriptHashCache.set(path, script.hash);
  return script.hash;
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function getResult(uuid: string): Promise<any> {
  for (;;) {
    const res = await JobService.getCompletedJobResultMaybe({
      workspace: workspace,
      id: uuid,
    });
    if (res.completed) {
      return res.result;
    }
    await delay(100);
  }
}
