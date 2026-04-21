"use client";

import { useMemo, useState } from "react";

import { AlertCircle, AlertTriangle, CheckCircle2, Info, Save, Wand2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { JsonEditor } from "@/components/ui/json-editor";
import { JsonTree } from "@/components/ui/json-tree";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/ui/loading-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  useEffectivePolicy,
  usePolicyFindings,
  usePolicyPacks,
  useProjectPolicy,
  useUpdateProjectPolicy,
} from "@/lib/api";
import type { EffectivePolicy, PolicyConfig, PolicyFinding, PolicyPack } from "@/lib/api/types";
import { truncateHash } from "@/lib/format";

interface PolicyTabProps {
  projectId: number;
}

export function PolicyTab({ projectId }: PolicyTabProps) {
  const { data: policy, isLoading: policyLoading } = useProjectPolicy(projectId);
  const { data: packs, isLoading: packsLoading } = usePolicyPacks();
  const { data: effective } = useEffectivePolicy(projectId);
  const { data: findings } = usePolicyFindings(projectId);
  const updatePolicy = useUpdateProjectPolicy();

  if (policyLoading || packsLoading) return <LoadingState message="Loading policy..." />;

  return (
    <PolicyForm
      key={`${policy?.policy_pack_key ?? "none"}:${policy?.policy_pack_version ?? "none"}`}
      projectId={projectId}
      policy={policy}
      packs={packs ?? []}
      effective={effective}
      findings={findings}
      updatePolicy={updatePolicy}
    />
  );
}

type UpdatePolicyMutation = ReturnType<typeof useUpdateProjectPolicy>;

interface PolicyFormProps {
  projectId: number;
  policy: PolicyConfig | undefined;
  packs: PolicyPack[];
  effective: EffectivePolicy | undefined;
  findings: PolicyFinding[] | undefined;
  updatePolicy: UpdatePolicyMutation;
}

function PolicyForm({
  projectId,
  policy,
  packs,
  effective,
  findings,
  updatePolicy,
}: PolicyFormProps) {
  const [formData, setFormData] = useState<Partial<PolicyConfig>>(() => ({
    policy_pack_key: policy?.policy_pack_key ?? null,
    policy_pack_version: policy?.policy_pack_version ?? null,
    policy_overrides: policy?.policy_overrides ?? null,
    policy_repo_local_enabled: policy?.policy_repo_local_enabled ?? false,
    policy_enforcement_mode: policy?.policy_enforcement_mode ?? "off",
  }));
  const [overridesJson, setOverridesJson] = useState(() =>
    policy?.policy_overrides ? JSON.stringify(policy.policy_overrides, null, 2) : "{}"
  );

  const packsByKey = useMemo(() => {
    const map = new Map<string, PolicyPack[]>();
    for (const pack of packs) {
      if (!pack.key) continue;
      const list = map.get(pack.key) ?? [];
      list.push(pack);
      map.set(pack.key, list);
    }
    for (const [key, list] of map.entries()) {
      list.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
      map.set(key, list);
    }
    return map;
  }, [packs]);

  const selectedPackKey = formData.policy_pack_key ?? null;
  const selectedPackVersion = formData.policy_pack_version ?? null;
  const selectedPack = useMemo(() => {
    if (!selectedPackKey) return null;
    const candidates = packsByKey.get(selectedPackKey) ?? [];
    if (!selectedPackVersion) return candidates[0] ?? null;
    return candidates.find((p) => p.version === selectedPackVersion) ?? candidates[0] ?? null;
  }, [packsByKey, selectedPackKey, selectedPackVersion]);

  const packOptions = useMemo(
    () =>
      Array.from(packsByKey.entries())
        .map(([key, list]) => ({ key, pack: list[0] }))
        .sort((a, b) => a.pack.name.localeCompare(b.pack.name)),
    [packsByKey]
  );

  const parsedOverrides = useMemo(() => {
    const raw = (overridesJson ?? "").trim();
    if (!raw || raw === "{}") {
      return { value: null as Record<string, unknown> | null, error: null as string | null };
    }
    try {
      const value = JSON.parse(raw) as Record<string, unknown>;
      if (value == null || typeof value !== "object" || Array.isArray(value)) {
        return { value: null, error: "Overrides must be a JSON object." };
      }
      return { value, error: null };
    } catch (e) {
      return { value: null, error: e instanceof Error ? e.message : "Invalid JSON" };
    }
  }, [overridesJson]);

  const handleFormatJson = () => {
    try {
      const raw = (overridesJson ?? "").trim();
      if (!raw) {
        setOverridesJson("{}");
        return;
      }
      const value = JSON.parse(raw);
      setOverridesJson(JSON.stringify(value, null, 2));
      toast.success("Formatted JSON");
    } catch {
      toast.error("Cannot format: invalid JSON");
    }
  };

  const handleSave = async () => {
    try {
      if (parsedOverrides.error) {
        toast.error(`Overrides JSON invalid: ${parsedOverrides.error}`);
        return;
      }
      let overrides = null;
      if (parsedOverrides.value) {
        overrides = parsedOverrides.value;
      }
      await updatePolicy.mutateAsync({
        projectId,
        policy: {
          ...formData,
          policy_overrides: overrides,
        },
      });
      toast.success("Policy updated successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update policy");
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Policy Configuration</CardTitle>
          <CardDescription>Configure policy pack and enforcement settings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Policy Pack</Label>
              <Select
                value={formData.policy_pack_key || "none"}
                onValueChange={(v) =>
                  setFormData((p) => {
                    if (!v || v === "none") {
                      return { ...p, policy_pack_key: null, policy_pack_version: null };
                    }
                    const candidates = packsByKey.get(v) ?? [];
                    const defaultVersion = candidates[0]?.version ?? null;
                    return { ...p, policy_pack_key: v, policy_pack_version: defaultVersion };
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select policy pack" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  {packOptions.map(({ key, pack }) => (
                    <SelectItem key={key} value={key}>
                      {pack.name} ({pack.key}) • latest
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Policy Pack Version</Label>
              <Select
                value={formData.policy_pack_version || "latest"}
                onValueChange={(v) =>
                  setFormData((p) => ({ ...p, policy_pack_version: v === "latest" ? null : v }))
                }
                disabled={!selectedPackKey}
              >
                <SelectTrigger>
                  <SelectValue
                    placeholder={selectedPackKey ? "Select version" : "Select a policy pack first"}
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="latest">Latest</SelectItem>
                  {(selectedPackKey ? (packsByKey.get(selectedPackKey) ?? []) : []).map((pack) => (
                    <SelectItem key={`${pack.key}:${pack.version}`} value={pack.version}>
                      {pack.version} • {pack.status}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Enforcement Mode</Label>
              <Select
                value={formData.policy_enforcement_mode || "off"}
                onValueChange={(v) =>
                  setFormData((p) => ({
                    ...p,
                    policy_enforcement_mode: v as PolicyConfig["policy_enforcement_mode"],
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="off">Off</SelectItem>
                  <SelectItem value="warn">Warn</SelectItem>
                  <SelectItem value="block">Enforce</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Switch
              id="repo_local"
              checked={formData.policy_repo_local_enabled || false}
              onCheckedChange={(v) => setFormData((p) => ({ ...p, policy_repo_local_enabled: v }))}
            />
            <Label htmlFor="repo_local" className="text-sm">
              Enable repo-local override (.devgodzilla/policy.yml)
            </Label>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label>Policy Overrides (JSON)</Label>
              <div className="flex items-center gap-2">
                {parsedOverrides.error ? (
                  <div className="flex items-center gap-1 text-xs text-red-600">
                    <AlertCircle className="h-3.5 w-3.5" />
                    Invalid JSON
                  </div>
                ) : (
                  <div className="flex items-center gap-1 text-xs text-green-600">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Valid
                  </div>
                )}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleFormatJson}
                  className="h-7 px-2"
                >
                  <Wand2 className="mr-1 h-3.5 w-3.5" />
                  Format
                </Button>
              </div>
            </div>
            <JsonEditor value={overridesJson} onChange={setOverridesJson} height={280} />
            {parsedOverrides.error && (
              <div className="text-xs text-red-600">Parse error: {parsedOverrides.error}</div>
            )}
            <div className="text-muted-foreground text-xs">
              Example:{" "}
              <span className="font-mono">{`{ "defaults": { "models": { "exec": "codex-5.1-max" } } }`}</span>
            </div>
          </div>

          <Button
            onClick={handleSave}
            disabled={updatePolicy.isPending || Boolean(parsedOverrides.error)}
          >
            <Save className="mr-2 h-4 w-4" />
            {updatePolicy.isPending ? "Saving..." : "Save Policy"}
          </Button>
        </CardContent>
      </Card>

      {selectedPack && (
        <Card>
          <CardHeader>
            <CardTitle>Policy Pack Preview</CardTitle>
            <CardDescription>
              {selectedPack.name} • {selectedPack.key} • {selectedPack.version}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {selectedPack.description && (
              <p className="text-muted-foreground text-sm">{selectedPack.description}</p>
            )}
            <CodeBlock code={selectedPack.pack} title="Pack Contents" maxHeight="300px" />
          </CardContent>
        </Card>
      )}

      {parsedOverrides.value && (
        <Card>
          <CardHeader>
            <CardTitle>Overrides Tree</CardTitle>
            <CardDescription>Quick visual inspection of your overrides</CardDescription>
          </CardHeader>
          <CardContent>
            <JsonTree value={parsedOverrides.value} rootName="policy_overrides" />
          </CardContent>
        </Card>
      )}

      {effective && (
        <Card>
          <CardHeader>
            <CardTitle>Effective Policy</CardTitle>
            <CardDescription>Hash: {truncateHash(effective.hash, 16)}</CardDescription>
          </CardHeader>
          <CardContent>
            <CodeBlock code={effective.policy} title="Effective Policy JSON" maxHeight="300px" />
          </CardContent>
        </Card>
      )}

      {findings && findings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Policy Findings</CardTitle>
            <CardDescription>{findings.length} finding(s)</CardDescription>
          </CardHeader>
          <CardContent>
            <FindingsList findings={findings} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function FindingsList({ findings }: { findings: PolicyFinding[] }) {
  return (
    <div className="space-y-3">
      {findings.map((finding, index) => (
        <div key={index} className="flex items-start gap-3 rounded-lg border p-3">
          {finding.severity === "error" ? (
            <AlertCircle className="text-destructive mt-0.5 h-5 w-5" />
          ) : finding.severity === "warning" ? (
            <AlertTriangle className="mt-0.5 h-5 w-5 text-yellow-500" />
          ) : (
            <Info className="mt-0.5 h-5 w-5 text-blue-500" />
          )}
          <div className="min-w-0 flex-1">
            <p className="text-muted-foreground font-mono text-sm">{finding.code}</p>
            <p className="mt-1">{finding.message}</p>
            {finding.location && (
              <p className="text-muted-foreground mt-1 text-sm">Location: {finding.location}</p>
            )}
            {finding.suggested_fix && (
              <p className="text-muted-foreground mt-1 text-sm">
                Suggested fix: {finding.suggested_fix}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
