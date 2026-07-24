import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { AssetType, ControlType, TechniqueType, WorkflowDef } from "../api/types";

const BADGE: Record<string, [string, string]> = {
  red: ["badge-red", "Red Team"], blue: ["badge-blue", "Blue Team"], purple: ["badge-purple", "Purple Team"],
  soc: ["badge-green", "SOC"], ics: ["badge-orange", "ICS/OT"], cloud: ["badge-teal", "Cloud"],
};
const ZONES = ["perimeter", "corp", "soc", "cloud", "ot_dmz", "ot"] as const;
const ZONE_LABEL: Record<string, string> = { perimeter: "Perimeter", corp: "Corporate", soc: "SOC", cloud: "Cloud", ot_dmz: "OT DMZ", ot: "OT" };
const SEV_COLOR: Record<string, string> = { critical: "var(--gc-red)", high: "var(--gc-orange)", medium: "var(--gc-yellow)", low: "var(--gc-green)" };
const TACTIC_ORDER = ["Reconnaissance", "Initial Access", "Command and Control", "Credential Access",
  "Privilege Escalation", "Lateral Movement", "Persistence", "Collection", "Exfiltration",
  "Defense Evasion", "Impact", "Lateral Movement (ICS)", "Impair Process Control (ICS)"];

interface DetectionSignal {
  indicator_type: string; signal: string; detection_source: string; expected_priority: string;
}
interface Step {
  id: string; technique: string; phase: string; at_min: number;
  by: string; value: string; is_inject: boolean; label: string;
  fallback_technique?: string; persistence_type?: string;
  expected_detections?: DetectionSignal[];
}

const INDICATOR_TYPES = ["Behavioural", "Network", "Active Directory", "Registry", "Data Access"];
const DETECTION_SOURCES = ["EDR", "SIEM", "Firewall/IDS", "NDR", "DLP", "AD Audit Logs", "DNS Firewall", "AV"];
const P_LEVELS = ["P0", "P1", "P2", "P3"];
const DECISION_GATES = [
  { id: "gate_single_endpoint", name: "Single endpoint — isolate immediately", trigger: "single_endpoint",
    risk: "low", desc: "Isolate via EDR immediately. Preserve memory first.", irp: "IRP 3.1" },
  { id: "gate_dc_no_isolate", name: "DC compromised — CISO approval required", trigger: "dc_compromised",
    risk: "extreme", desc: "Do NOT isolate DC without CISO approval — breaks all auth.", irp: "IRP 3.1" },
  { id: "gate_multi_host", name: "Multi-host — contain confirmed only", trigger: "multi_host",
    risk: "medium", desc: "Isolate confirmed hosts. Monitor suspected passively. No network-wide isolation.", irp: "IRP 3.1" },
  { id: "gate_ransomware_segment", name: "Ransomware — emergency VLAN segmentation", trigger: "ransomware_spreading",
    risk: "extreme", desc: "Segment network immediately. Isolate affected VLAN. Prioritise un-encrypted systems.", irp: "IRP 3.1" },
  { id: "gate_exfil_egress_first", name: "Active exfil — block egress before host", trigger: "active_exfil",
    risk: "low", desc: "Block egress IP/domain at firewall first. Do NOT isolate source host until egress blocked.", irp: "IRP B.C.02" },
];
const RISK_COLOR: Record<string, string> = { low: "var(--gc-green)", medium: "var(--gc-yellow)", high: "var(--gc-orange)", extreme: "var(--gc-red)" };

const REG_FRAMEWORKS = [
  { id: "ndb", name: "NDB Scheme (Data Breach)", jurisdiction: "Australia", trigger: "data_breach",
    deadline: "30 days", penalty: "Up to AUD $50M", industries: ["all"] },
  { id: "apra_cps234", name: "APRA CPS 234", jurisdiction: "Australia — Financial", trigger: "financial",
    deadline: "72 hours", penalty: "Regulatory sanctions", industries: ["finance"] },
  { id: "swift_csp", name: "SWIFT CSP", jurisdiction: "Global — Financial", trigger: "financial",
    deadline: "Immediately", penalty: "Network removal", industries: ["finance"] },
  { id: "critical_infra", name: "Critical Infrastructure Act (SOCI)", jurisdiction: "Australia", trigger: "critical_infra",
    deadline: "12h severe / 72h significant", penalty: "Civil penalties", industries: ["manufacturing", "energy", "healthcare"] },
  { id: "austrac", name: "AUSTRAC AML/CTF", jurisdiction: "Australia — Financial", trigger: "financial",
    deadline: "Same day", penalty: "Up to AUD $22.2M", industries: ["finance"] },
  { id: "asx_listing", name: "ASX Listing Rules 3.1", jurisdiction: "Australia — Listed", trigger: "any_material",
    deadline: "Immediately", penalty: "Fines, trading halt", industries: ["finance"] },
];
const INDUSTRY_FW_MAP: Record<string, string[]> = {
  finance: ["ndb", "apra_cps234", "swift_csp", "austrac", "asx_listing"],
  manufacturing: ["ndb", "critical_infra"],
  energy: ["ndb", "critical_infra"],
  healthcare: ["ndb", "critical_infra"],
  generic: ["ndb"],
};

const PERSISTENCE_TYPES = [
  { key: "registry_run_key", label: "Registry Run Key" },
  { key: "scheduled_task", label: "Scheduled Task" },
  { key: "process_injection", label: "Process Injection (LSASS)" },
  { key: "rogue_account", label: "Rogue AD Account" },
  { key: "golden_ticket", label: "Golden Ticket (krbtgt)" },
  { key: "log_deletion", label: "Log Deletion / Anti-forensics" },
];

let stepCounter = 0;
function nextStepId() { return `s${++stepCounter}`; }

// Pre-built attack chain templates
const TEMPLATES: { name: string; icon: string; desc: string; phases: string[]; steps: Omit<Step, "id">[]; assets: string[]; }[] = [
  { name: "APT Full Kill Chain", icon: "fa-skull-crossbones", desc: "8-phase APT: recon to OT impact",
    phases: ["Reconnaissance", "Initial Compromise", "Privilege Escalation", "Lateral Movement", "Persistence", "Data Exfiltration", "Ransomware", "OT Attack"],
    assets: ["endpoint", "domain_controller", "email_server", "file_share", "erp", "mes", "ot_plc", "cloud", "siem_platform", "edr_platform", "firewall"],
    steps: [
      { technique: "recon_osint", phase: "Reconnaissance", at_min: 1, by: "type", value: "", is_inject: false, label: "" },
      { technique: "phishing", phase: "Initial Compromise", at_min: 4, by: "role", value: "primary_endpoint", is_inject: true, label: "Spear-phishing from supplier domain" },
      { technique: "c2_beacon", phase: "Initial Compromise", at_min: 6, by: "role", value: "primary_endpoint", is_inject: false, label: "" },
      { technique: "credential_dump", phase: "Privilege Escalation", at_min: 9, by: "role", value: "primary_endpoint", is_inject: false, label: "" },
      { technique: "kerberoasting", phase: "Privilege Escalation", at_min: 11, by: "type", value: "domain_controller", is_inject: false, label: "" },
      { technique: "dcsync_domain_admin", phase: "Privilege Escalation", at_min: 14, by: "type", value: "domain_controller", is_inject: false, label: "" },
      { technique: "lateral_movement", phase: "Lateral Movement", at_min: 17, by: "role", value: "sensitive_share", is_inject: false, label: "" },
      { technique: "lateral_movement", phase: "Lateral Movement", at_min: 19, by: "type", value: "erp", is_inject: false, label: "" },
      { technique: "persistence_task", phase: "Persistence", at_min: 22, by: "role", value: "primary_endpoint", is_inject: false, label: "" },
      { technique: "cloud_persistence", phase: "Persistence", at_min: 25, by: "type", value: "cloud", is_inject: false, label: "" },
      { technique: "collection_staging", phase: "Data Exfiltration", at_min: 30, by: "role", value: "sensitive_share", is_inject: false, label: "" },
      { technique: "exfiltration", phase: "Data Exfiltration", at_min: 34, by: "role", value: "sensitive_share", is_inject: false, label: "" },
      { technique: "disable_security_tools", phase: "Ransomware", at_min: 40, by: "role", value: "primary_endpoint", is_inject: false, label: "" },
      { technique: "ransomware", phase: "Ransomware", at_min: 45, by: "type", value: "erp", is_inject: true, label: "Ransomware detonation" },
      { technique: "ot_pivot", phase: "OT Attack", at_min: 52, by: "type", value: "mes", is_inject: false, label: "" },
      { technique: "ot_plc_modify", phase: "OT Attack", at_min: 58, by: "type", value: "ot_plc", is_inject: false, label: "" },
    ] },
  { name: "Ransomware Only", icon: "fa-lock", desc: "Fast ransomware: phish to encrypt in 6 steps",
    phases: ["Initial Compromise", "Privilege Escalation", "Ransomware"],
    assets: ["endpoint", "domain_controller", "file_share", "erp", "edr_platform", "siem_platform"],
    steps: [
      { technique: "phishing", phase: "Initial Compromise", at_min: 3, by: "role", value: "primary_endpoint", is_inject: true, label: "" },
      { technique: "c2_beacon", phase: "Initial Compromise", at_min: 5, by: "role", value: "primary_endpoint", is_inject: false, label: "" },
      { technique: "credential_dump", phase: "Privilege Escalation", at_min: 10, by: "role", value: "primary_endpoint", is_inject: false, label: "" },
      { technique: "kerberoasting", phase: "Privilege Escalation", at_min: 14, by: "type", value: "domain_controller", is_inject: false, label: "" },
      { technique: "disable_security_tools", phase: "Ransomware", at_min: 20, by: "role", value: "primary_endpoint", is_inject: false, label: "" },
      { technique: "ransomware", phase: "Ransomware", at_min: 25, by: "type", value: "erp", is_inject: true, label: "Ransomware detonation" },
    ] },
  { name: "Data Theft (Insider)", icon: "fa-user-secret", desc: "Credential theft and exfiltration focus",
    phases: ["Initial Compromise", "Privilege Escalation", "Data Exfiltration"],
    assets: ["endpoint", "domain_controller", "file_share", "cloud", "siem_platform", "edr_platform"],
    steps: [
      { technique: "phishing", phase: "Initial Compromise", at_min: 3, by: "role", value: "primary_endpoint", is_inject: true, label: "" },
      { technique: "c2_beacon", phase: "Initial Compromise", at_min: 6, by: "role", value: "primary_endpoint", is_inject: false, label: "" },
      { technique: "credential_dump", phase: "Privilege Escalation", at_min: 12, by: "role", value: "primary_endpoint", is_inject: false, label: "" },
      { technique: "dcsync_domain_admin", phase: "Privilege Escalation", at_min: 18, by: "type", value: "domain_controller", is_inject: false, label: "" },
      { technique: "lateral_movement", phase: "Privilege Escalation", at_min: 22, by: "role", value: "sensitive_share", is_inject: false, label: "" },
      { technique: "collection_staging", phase: "Data Exfiltration", at_min: 28, by: "role", value: "sensitive_share", is_inject: false, label: "" },
      { technique: "exfiltration", phase: "Data Exfiltration", at_min: 35, by: "role", value: "sensitive_share", is_inject: true, label: "DLP alert: large outbound transfer" },
    ] },
  { name: "OT/ICS Attack", icon: "fa-industry", desc: "IT compromise pivoting into OT/manufacturing",
    phases: ["Initial Compromise", "Privilege Escalation", "Lateral Movement", "OT Attack"],
    assets: ["endpoint", "domain_controller", "mes", "ot_plc", "firewall", "siem_platform", "edr_platform"],
    steps: [
      { technique: "phishing", phase: "Initial Compromise", at_min: 3, by: "role", value: "primary_endpoint", is_inject: true, label: "" },
      { technique: "c2_beacon", phase: "Initial Compromise", at_min: 6, by: "role", value: "primary_endpoint", is_inject: false, label: "" },
      { technique: "credential_dump", phase: "Privilege Escalation", at_min: 10, by: "role", value: "primary_endpoint", is_inject: false, label: "" },
      { technique: "dcsync_domain_admin", phase: "Privilege Escalation", at_min: 16, by: "type", value: "domain_controller", is_inject: false, label: "" },
      { technique: "lateral_movement", phase: "Lateral Movement", at_min: 22, by: "type", value: "mes", is_inject: false, label: "IT/OT boundary crossing" },
      { technique: "ot_pivot", phase: "OT Attack", at_min: 30, by: "type", value: "mes", is_inject: false, label: "" },
      { technique: "ot_plc_modify", phase: "OT Attack", at_min: 38, by: "type", value: "ot_plc", is_inject: true, label: "PLC setpoint manipulation" },
    ] },
];

export default function Builder() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const cloneFrom = params.get("clone");

  const assets = useQuery<AssetType[]>({ queryKey: ["assets"], queryFn: api.assets });
  const controls = useQuery<ControlType[]>({ queryKey: ["controls"], queryFn: api.controls });
  const techniques = useQuery<TechniqueType[]>({ queryKey: ["techniques"], queryFn: api.techniques });
  const workflows = useQuery<WorkflowDef[]>({ queryKey: ["workflows"], queryFn: api.workflows });
  const cloneData = useQuery({ queryKey: ["clone", cloneFrom], queryFn: () => api.scenario(cloneFrom!), enabled: !!cloneFrom });

  const [name, setName] = useState("");
  const [type, setType] = useState("purple");
  const [industry, setIndustry] = useState("generic");
  const [duration, setDuration] = useState(90);
  const [description, setDescription] = useState("");
  const [pickedAssets, setPickedAssets] = useState<{ id: string; type: string; name: string; zone: string; criticality: number }[]>([]);
  const [pickedControls, setPickedControls] = useState<Set<string>>(new Set(["edr", "siem", "firewall_ids"]));
  const [phases, setPhases] = useState<string[]>(["Reconnaissance", "Initial Compromise"]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [objectives, setObjectives] = useState<Record<string, string>>({ red: "", blue: "", soc: "", mgmt: "", ot: "" });
  const [regFrameworks, setRegFrameworks] = useState<Set<string>>(new Set(["ndb"]));
  const [decisionGates, setDecisionGates] = useState<Set<string>>(new Set([
    "gate_single_endpoint", "gate_dc_no_isolate", "gate_multi_host", "gate_ransomware_segment", "gate_exfil_egress_first",
  ]));
  const [wfBindings, setWfBindings] = useState<Record<string, string>>({
    red: "apt_ransomware_killchain", soc: "tiered_triage_escalation",
    blue: "nist_ir_response", mgmt: "exec_escalation_regulatory", ot: "ot_safety_ops",
  });
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"templates" | "playbook" | "environment" | "objectives">("templates");
  const [techFilter, setTechFilter] = useState("");
  const [tacticFilter, setTacticFilter] = useState("");
  const [newPhase, setNewPhase] = useState("");
  const [dragIdx, setDragIdx] = useState<number | null>(null);

  // Clone scenario data
  useEffect(() => {
    if (!cloneData.data) return;
    const d = cloneData.data;
    setName(d.name + " (copy)");
    setType(d.type || "purple");
    setIndustry(d.industry || "generic");
    setDuration(d.nominal_duration_min || 90);
    setDescription(d.description || "");
    setPhases(d.phases || []);
    if (d.workflow_bindings) setWfBindings(d.workflow_bindings);
    if (d.recommended_topology?.assets) {
      setPickedAssets(d.recommended_topology.assets.map((a: any) => ({
        id: a.id, type: a.type, name: a.name || a.type, zone: a.zone || "corp", criticality: a.criticality || 3,
      })));
    }
    if (d.recommended_topology?.controls) {
      setPickedControls(new Set(d.recommended_topology.controls.filter((c: any) => c.enabled).map((c: any) => c.type)));
    }
    if (d.playbook) {
      setSteps(d.playbook.map((s: any, i: number) => ({
        id: s.id || `s${i + 1}`, technique: s.technique, phase: s.phase, at_min: s.at_min || 0,
        by: s.target?.by || "type", value: s.target?.value || "", is_inject: s.is_inject || false, label: s.label || "",
        fallback_technique: s.fallback_technique || "", persistence_type: s.persistence_type || "",
        expected_detections: s.expected_detections || [],
      })));
      stepCounter = d.playbook.length;
    }
    if (d.objectives) {
      setObjectives({
        red: (d.objectives.red || []).join("\n"), blue: (d.objectives.blue || []).join("\n"),
        soc: (d.objectives.soc || []).join("\n"), mgmt: (d.objectives.mgmt || []).join("\n"),
        ot: (d.objectives.ot || []).join("\n"),
      });
    }
  }, [cloneData.data]);

  // Group techniques by tactic
  const techByTactic = useMemo(() => {
    const m: Record<string, TechniqueType[]> = {};
    for (const t of techniques.data ?? []) {
      (m[t.tactic] ??= []).push(t);
    }
    return m;
  }, [techniques.data]);

  const techMap = useMemo(() => {
    const m: Record<string, TechniqueType> = {};
    for (const t of techniques.data ?? []) m[t.key] = t;
    return m;
  }, [techniques.data]);

  const assetCatMap = useMemo(() => {
    const m: Record<string, AssetType> = {};
    for (const a of assets.data ?? []) m[a.key] = a;
    return m;
  }, [assets.data]);

  // Validation warnings
  const warnings = useMemo(() => {
    const w: string[] = [];
    if (steps.length === 0) w.push("Add at least one attack step");
    if (phases.length === 0) w.push("Define at least one phase");
    for (const s of steps) {
      if (!s.technique) w.push(`Step ${s.id}: no technique selected`);
      if (s.phase && !phases.includes(s.phase)) w.push(`Step ${s.id}: phase "${s.phase}" not in phase list`);
    }
    // Check precondition chain
    const techs = steps.map(s => s.technique).filter(Boolean);
    if (techs.includes("lateral_movement") && !techs.some(t => ["credential_dump", "kerberoasting", "dcsync_domain_admin"].includes(t))) {
      w.push("Lateral movement requires privileged credentials - add a credential technique first");
    }
    if (techs.includes("exfiltration") && !techs.includes("collection_staging")) {
      w.push("Exfiltration requires data staging first");
    }
    if (techs.includes("ot_plc_modify") && !techs.includes("ot_pivot")) {
      w.push("PLC modification requires IT/OT pivot first");
    }
    if (techs.includes("ransomware") && !techs.some(t => ["credential_dump", "kerberoasting"].includes(t))) {
      w.push("Ransomware requires privileged credentials");
    }
    return w;
  }, [steps, phases]);

  const addAsset = (type: string) => {
    const at = assetCatMap[type];
    if (!at) return;
    const count = pickedAssets.filter(a => a.type === type).length;
    setPickedAssets(prev => [...prev, {
      id: `${type}-${count + 1}`, type, name: at.name, zone: at.default_zone, criticality: at.default_criticality,
    }]);
  };

  const removeAsset = (id: string) => setPickedAssets(prev => prev.filter(a => a.id !== id));

  const updateAsset = (id: string, patch: Partial<typeof pickedAssets[0]>) =>
    setPickedAssets(prev => prev.map(a => a.id === id ? { ...a, ...patch } : a));

  const toggleControl = (type: string) =>
    setPickedControls(s => { const n = new Set(s); n.has(type) ? n.delete(type) : n.add(type); return n; });

  const addPhase = () => {
    if (!newPhase.trim() || phases.includes(newPhase.trim())) return;
    setPhases(prev => [...prev, newPhase.trim()]);
    setNewPhase("");
  };

  const removePhase = (p: string) => setPhases(prev => prev.filter(x => x !== p));

  const addStep = (technique?: string, tactic?: string) => {
    const phase = tactic ? (phases.find(p => p.toLowerCase().includes(tactic.toLowerCase().split(" ")[0])) || phases[0] || "") : (phases[0] || "");
    const maxMin = steps.length > 0 ? Math.max(...steps.map(s => s.at_min)) : 0;
    setSteps(prev => [...prev, {
      id: nextStepId(), technique: technique || "", phase, at_min: maxMin + 5,
      by: "type", value: "", is_inject: false, label: "",
      fallback_technique: "", persistence_type: "", expected_detections: [],
    }]);
  };

  const updateStep = (i: number, patch: Partial<Step>) =>
    setSteps(s => s.map((st, j) => j === i ? { ...st, ...patch } : st));

  const removeStep = (i: number) => setSteps(s => s.filter((_, j) => j !== i));

  const moveStep = (from: number, to: number) => {
    if (to < 0 || to >= steps.length) return;
    setSteps(prev => {
      const n = [...prev];
      const [item] = n.splice(from, 1);
      n.splice(to, 0, item);
      return n;
    });
  };

  const autoTimeline = () => {
    setSteps(prev => prev.map((s, i) => ({ ...s, at_min: (i + 1) * Math.round(duration / (prev.length + 1)) })));
  };

  const loadTemplate = (tmpl: typeof TEMPLATES[0]) => {
    if (steps.length > 0 && !confirm("This will replace your current playbook. Continue?")) return;
    setPhases(tmpl.phases);
    stepCounter = 0;
    setSteps(tmpl.steps.map(s => ({ ...s, id: nextStepId(), fallback_technique: "", persistence_type: "", expected_detections: [] })));
    // Auto-add recommended assets if none
    if (pickedAssets.length === 0) {
      const newAssets: typeof pickedAssets = [];
      for (const type of tmpl.assets) {
        const at = assetCatMap[type];
        if (at) newAssets.push({ id: `${type}-1`, type, name: at.name, zone: at.default_zone, criticality: at.default_criticality });
      }
      setPickedAssets(newAssets);
    }
    setActiveTab("playbook");
  };

  const exportJSON = () => {
    const scenario = {
      name, type, industry, nominal_duration_min: duration, description, phases,
      workflow_bindings: wfBindings,
      recommended_topology: {
        assets: pickedAssets.map(a => ({ id: a.id, type: a.type, name: a.name, zone: a.zone, criticality: a.criticality })),
        controls: [...pickedControls].map(t => ({ id: `c-${t}`, type: t, enabled: true })),
      },
      playbook: steps.filter(s => s.technique).map(s => ({
        id: s.id, technique: s.technique, phase: s.phase, at_min: s.at_min,
        target: s.value ? { by: s.by, value: s.value } : null,
        is_inject: s.is_inject, label: s.label || null,
      })),
      objectives,
    };
    const blob = new Blob([JSON.stringify(scenario, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url;
    a.download = `${name.replace(/\s+/g, "_") || "scenario"}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  const importJSON = () => {
    const input = document.createElement("input"); input.type = "file"; input.accept = ".json";
    input.onchange = async () => {
      const file = input.files?.[0]; if (!file) return;
      const text = await file.text();
      try {
        const d = JSON.parse(text);
        if (d.name) setName(d.name);
        if (d.type) setType(d.type);
        if (d.industry) setIndustry(d.industry);
        if (d.nominal_duration_min) setDuration(d.nominal_duration_min);
        if (d.description) setDescription(d.description);
        if (d.phases) setPhases(d.phases);
        if (d.workflow_bindings) setWfBindings(d.workflow_bindings);
        if (d.recommended_topology?.assets) setPickedAssets(d.recommended_topology.assets);
        if (d.recommended_topology?.controls) setPickedControls(new Set(d.recommended_topology.controls.map((c: any) => c.type)));
        if (d.playbook) {
          stepCounter = 0;
          setSteps(d.playbook.map((s: any) => ({
            id: s.id || nextStepId(), technique: s.technique, phase: s.phase, at_min: s.at_min || 0,
            by: s.target?.by || "type", value: s.target?.value || "", is_inject: s.is_inject || false, label: s.label || "",
            fallback_technique: s.fallback_technique || "", persistence_type: s.persistence_type || "",
            expected_detections: s.expected_detections || [],
          })));
        }
        if (d.objectives) setObjectives({ red: "", blue: "", soc: "", mgmt: "", ot: "", ...d.objectives });
        setActiveTab("playbook");
      } catch (e) { alert("Invalid JSON: " + e); }
    };
    input.click();
  };

  // Stats
  const scenarioStats = useMemo(() => {
    const tactics = new Set(steps.map(s => techMap[s.technique]?.tactic).filter(Boolean));
    const injects = steps.filter(s => s.is_inject).length;
    const critSteps = steps.filter(s => techMap[s.technique]?.severity === "critical").length;
    const highSteps = steps.filter(s => techMap[s.technique]?.severity === "high").length;
    const maxMin = steps.length > 0 ? Math.max(...steps.map(s => s.at_min)) : 0;
    const targetedAssetTypes = new Set(steps.map(s => s.value).filter(Boolean));
    return { tactics: tactics.size, injects, critSteps, highSteps, maxMin, targetedAssetTypes: targetedAssetTypes.size };
  }, [steps, techMap]);

  const save = async () => {
    const id = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || `custom_${Date.now()}`;
    if (phases.length === 0) { alert("Define at least one phase."); return; }
    if (steps.length === 0) { alert("Add at least one step."); return; }

    const assetSpecs = pickedAssets.map(a => ({
      id: a.id, type: a.type, name: a.name, zone: a.zone, criticality: a.criticality,
    }));
    const controlSpecs = [...pickedControls].map(t => ({ id: `c-${t}`, type: t, enabled: true }));

    const scenario = {
      schema_version: 1, id, name: name || "Custom Scenario", type, industry,
      badge: (BADGE[type] ?? BADGE.purple)[0], label: (BADGE[type] ?? BADGE.purple)[1],
      description: description || name, difficulties: ["Easy", "Medium", "Hard", "Expert"],
      nominal_duration_min: duration,
      mitre_tactics: [...new Set(steps.map(s => techMap[s.technique]?.tactic).filter(Boolean))],
      phases,
      recommended_topology: { assets: assetSpecs, controls: controlSpecs },
      workflow_bindings: wfBindings,
      regulatory_frameworks: [...regFrameworks],
      decision_gates: DECISION_GATES.filter(g => decisionGates.has(g.id)).map(g => ({
        id: g.id, name: g.name, trigger: g.trigger, correct_action: "auto",
        risk_level: g.risk, description: g.desc,
      })),
      playbook: steps.filter(s => s.technique).map(s => ({
        id: s.id, technique: s.technique, phase: s.phase, at_min: s.at_min,
        target: s.value ? { by: s.by, value: s.value, pick: "first" } : null,
        is_inject: s.is_inject, label: s.label || null,
        fallback_technique: s.fallback_technique || null,
        persistence_type: s.persistence_type || null,
        expected_detections: (s.expected_detections ?? []).length > 0 ? s.expected_detections : undefined,
      })),
      objectives: {
        red: objectives.red.split("\n").map(x => x.trim()).filter(Boolean),
        blue: objectives.blue.split("\n").map(x => x.trim()).filter(Boolean),
        soc: objectives.soc.split("\n").map(x => x.trim()).filter(Boolean),
        mgmt: objectives.mgmt.split("\n").map(x => x.trim()).filter(Boolean),
        ot: objectives.ot.split("\n").map(x => x.trim()).filter(Boolean),
      },
    };
    setSaving(true);
    try {
      const res = await fetch("/api/scenarios", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(scenario),
      });
      if (!res.ok) throw new Error(await res.text());
      nav(`/launch/${id}`);
    } catch (e) { alert("Save failed: " + e); setSaving(false); }
  };

  // Auto-suggest regulatory frameworks based on industry
  const suggestedFrameworks = useMemo(() => {
    return INDUSTRY_FW_MAP[industry.toLowerCase()] || INDUSTRY_FW_MAP.generic;
  }, [industry]);

  const filteredTactics = TACTIC_ORDER.filter(t => techByTactic[t]?.length);

  return (
    <>
      <div className="section-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div><h1>Scenario Builder</h1><p>Build a custom attack scenario with MITRE ATT&CK techniques, define the environment, and configure team objectives</p></div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-ghost" onClick={importJSON} style={{ fontSize: 11 }}><i className="fa fa-file-import" /> Import</button>
          <button className="btn btn-ghost" onClick={exportJSON} style={{ fontSize: 11 }} disabled={steps.length === 0}><i className="fa fa-file-export" /> Export</button>
          <button className="btn btn-ghost" onClick={() => nav("/library")}>Cancel</button>
          <button className="btn btn-primary" onClick={save} disabled={saving || !name || steps.length === 0}>
            {saving ? <><span className="spinner" /> Saving...</> : <><i className="fa fa-rocket" /> Save & Launch</>}
          </button>
        </div>
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div style={{ background: "rgba(255,214,0,.06)", border: "1px solid rgba(255,214,0,.2)", borderRadius: 8, padding: "10px 14px", marginBottom: 16 }}>
          {warnings.map((w, i) => (
            <div key={i} style={{ fontSize: 11, color: "var(--gc-yellow)", display: "flex", gap: 6, marginBottom: 2 }}>
              <i className="fa fa-exclamation-triangle" style={{ marginTop: 2, flexShrink: 0 }} /> {w}
            </div>
          ))}
        </div>
      )}

      {/* Top: Scenario Details */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-info-circle" /> Scenario Details</div>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 100px", gap: 12, marginBottom: 12 }}>
          <div><div className="builder-label">Name</div><input className="form-input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Finance Ransomware Drill" /></div>
          <div><div className="builder-label">Type</div>
            <select className="form-select" value={type} onChange={e => setType(e.target.value)}>
              {Object.keys(BADGE).map(t => <option key={t} value={t}>{BADGE[t][1]}</option>)}
            </select>
          </div>
          <div><div className="builder-label">Industry</div><input className="form-input" value={industry} onChange={e => setIndustry(e.target.value)} /></div>
          <div><div className="builder-label">Duration (min)</div><input className="form-input" type="number" value={duration} onChange={e => setDuration(+e.target.value)} /></div>
        </div>
        <div className="builder-label">Description</div>
        <textarea className="form-textarea" value={description} onChange={e => setDescription(e.target.value)} style={{ minHeight: 50 }} />
      </div>

      {/* Stats Strip */}
      {steps.length > 0 && (
        <div className="stats-row" style={{ marginBottom: 16 }}>
          <div className="stat-card accent"><div className="stat-label">Steps</div><div className="stat-value" style={{ fontSize: 20 }}>{steps.length}</div><div className="stat-sub">{scenarioStats.injects} injects</div></div>
          <div className="stat-card purple"><div className="stat-label">MITRE Tactics</div><div className="stat-value" style={{ fontSize: 20 }}>{scenarioStats.tactics}</div><div className="stat-sub">{phases.length} phases</div></div>
          <div className="stat-card red"><div className="stat-label">Critical/High</div><div className="stat-value" style={{ fontSize: 20 }}>{scenarioStats.critSteps}/{scenarioStats.highSteps}</div><div className="stat-sub">severity distribution</div></div>
          <div className="stat-card green"><div className="stat-label">Timeline</div><div className="stat-value" style={{ fontSize: 20 }}>{scenarioStats.maxMin}m</div><div className="stat-sub">{pickedAssets.length} assets, {pickedControls.size} controls</div></div>
        </div>
      )}

      {/* Visual Timeline */}
      {steps.length > 0 && (
        <div className="card" style={{ marginBottom: 16, padding: "12px 16px" }}>
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "var(--gc-muted)", marginBottom: 8 }}>Attack Timeline</div>
          <div style={{ position: "relative", height: 48, background: "var(--gc-surface)", borderRadius: 8, overflow: "hidden" }}>
            {/* Phase bands */}
            {phases.map((p, pi) => {
              const phaseSteps = steps.filter(s => s.phase === p);
              if (phaseSteps.length === 0) return null;
              const minT = Math.min(...phaseSteps.map(s => s.at_min));
              const maxT = Math.max(...phaseSteps.map(s => s.at_min));
              const total = scenarioStats.maxMin || 1;
              const left = (minT / total) * 100;
              const width = Math.max(((maxT - minT) / total) * 100, 2);
              const colors = ["rgba(0,212,255,.08)", "rgba(123,97,255,.08)", "rgba(255,112,67,.08)", "rgba(0,230,118,.08)",
                "rgba(255,214,0,.08)", "rgba(255,71,87,.08)", "rgba(77,208,225,.08)", "rgba(139,92,246,.08)"];
              return <div key={p} style={{ position: "absolute", left: `${left}%`, width: `${width}%`, top: 0, bottom: 0, background: colors[pi % colors.length], borderRight: "1px solid var(--gc-border)" }}>
                <div style={{ fontSize: 8, padding: "2px 4px", color: "var(--gc-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p}</div>
              </div>;
            })}
            {/* Step dots */}
            {steps.map((s, i) => {
              const total = scenarioStats.maxMin || 1;
              const left = (s.at_min / total) * 100;
              const tech = techMap[s.technique];
              const color = tech ? (SEV_COLOR[tech.severity] || "var(--gc-muted)") : "var(--gc-muted)";
              return <div key={s.id} title={`T+${s.at_min}m: ${tech?.name || s.technique || "empty"}`}
                style={{ position: "absolute", left: `${left}%`, bottom: 6, width: 10, height: 10, borderRadius: "50%",
                  background: color, border: s.is_inject ? "2px solid var(--gc-purple)" : "2px solid var(--gc-card)",
                  transform: "translateX(-5px)", cursor: "pointer", zIndex: 10 }} />;
            })}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: "var(--gc-muted)", marginTop: 4, fontFamily: "var(--mono)" }}>
            <span>T+0m</span><span>T+{scenarioStats.maxMin}m</span>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
        {(["templates", "playbook", "environment", "objectives"] as const).map(tab => (
          <button key={tab} className={"filter-chip" + (activeTab === tab ? " active" : "")} onClick={() => setActiveTab(tab)}
            style={{ textTransform: "capitalize", fontSize: 13, padding: "7px 16px" }}>
            <i className={`fa ${tab === "templates" ? "fa-wand-magic-sparkles" : tab === "playbook" ? "fa-bolt" : tab === "environment" ? "fa-server" : "fa-bullseye"}`} /> {tab}
            {tab === "playbook" && <span className="muted" style={{ marginLeft: 4 }}>({steps.length})</span>}
            {tab === "environment" && <span className="muted" style={{ marginLeft: 4 }}>({pickedAssets.length})</span>}
          </button>
        ))}
      </div>

      {/* TAB: Templates */}
      {activeTab === "templates" && (
        <div>
          <div style={{ fontSize: 13, color: "var(--gc-muted)", marginBottom: 16 }}>
            Start from a pre-built attack chain template, or build from scratch using the Playbook tab. Templates pre-populate phases, attack steps, and recommended assets.
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {TEMPLATES.map(tmpl => (
              <div key={tmpl.name} className="card" style={{ cursor: "pointer", transition: "all .15s", border: "1px solid var(--gc-border)" }}
                onClick={() => loadTemplate(tmpl)}
                onMouseEnter={e => (e.currentTarget.style.borderColor = "var(--gc-accent)")}
                onMouseLeave={e => (e.currentTarget.style.borderColor = "var(--gc-border)")}>
                <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: "rgba(0,212,255,.08)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <i className={`fa ${tmpl.icon}`} style={{ color: "var(--gc-accent)", fontSize: 16 }} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 700 }}>{tmpl.name}</div>
                    <div style={{ fontSize: 12, color: "var(--gc-muted)", marginTop: 2 }}>{tmpl.desc}</div>
                    <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                      <span className="tag" style={{ fontSize: 9 }}><i className="fa fa-layer-group" /> {tmpl.phases.length} phases</span>
                      <span className="tag" style={{ fontSize: 9 }}><i className="fa fa-bolt" /> {tmpl.steps.length} steps</span>
                      <span className="tag" style={{ fontSize: 9 }}><i className="fa fa-server" /> {tmpl.assets.length} assets</span>
                      {tmpl.steps.filter(s => s.is_inject).length > 0 && <span className="tag" style={{ fontSize: 9, background: "rgba(123,97,255,.12)", color: "var(--gc-purple)" }}><i className="fa fa-bolt" /> {tmpl.steps.filter(s => s.is_inject).length} injects</span>}
                    </div>
                    {/* Mini kill chain preview */}
                    <div style={{ display: "flex", gap: 3, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
                      {tmpl.phases.map((p, i) => (
                        <span key={p} style={{ display: "flex", alignItems: "center", gap: 3 }}>
                          <span style={{ fontSize: 9, padding: "2px 6px", borderRadius: 4, background: "var(--gc-surface)", border: "1px solid var(--gc-border)", whiteSpace: "nowrap" }}>{p}</span>
                          {i < tmpl.phases.length - 1 && <i className="fa fa-arrow-right" style={{ fontSize: 7, color: "var(--gc-muted)" }} />}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ))}

            {/* Blank scenario card */}
            <div className="card" style={{ cursor: "pointer", transition: "all .15s", border: "1px dashed var(--gc-border)", display: "flex", alignItems: "center", justifyContent: "center", minHeight: 120 }}
              onClick={() => setActiveTab("playbook")}
              onMouseEnter={e => (e.currentTarget.style.borderColor = "var(--gc-accent)")}
              onMouseLeave={e => (e.currentTarget.style.borderColor = "var(--gc-border)")}>
              <div style={{ textAlign: "center" }}>
                <i className="fa fa-plus" style={{ fontSize: 24, color: "var(--gc-muted)", marginBottom: 8, display: "block" }} />
                <div style={{ fontSize: 14, fontWeight: 600 }}>Start from scratch</div>
                <div style={{ fontSize: 11, color: "var(--gc-muted)" }}>Build your own attack playbook step by step</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB: Playbook */}
      {activeTab === "playbook" && (
        <div className="grid-2">
          {/* Left: Phase Manager + Steps */}
          <div>
            {/* Phase Manager */}
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header">
                <div className="card-title"><i className="fa fa-layer-group" /> Phases</div>
                <span className="muted" style={{ fontSize: 11 }}>{phases.length} phases</span>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
                {phases.map((p, i) => (
                  <div key={p} style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 10px", borderRadius: 6,
                    background: "var(--gc-surface)", border: "1px solid var(--gc-border)", fontSize: 12 }}>
                    <span style={{ color: "var(--gc-accent)", fontFamily: "var(--mono)", fontSize: 10 }}>{i + 1}</span>
                    <span>{p}</span>
                    <button onClick={() => removePhase(p)} style={{ background: "none", border: "none", color: "var(--gc-muted)", cursor: "pointer", padding: "0 2px" }}>
                      <i className="fa fa-times" style={{ fontSize: 9 }} />
                    </button>
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <input className="form-input" value={newPhase} onChange={e => setNewPhase(e.target.value)}
                  placeholder="New phase name..." style={{ flex: 1 }}
                  onKeyDown={e => e.key === "Enter" && addPhase()} />
                <button className="btn btn-ghost" onClick={addPhase} style={{ padding: "6px 12px", fontSize: 12 }}>
                  <i className="fa fa-plus" /> Add
                </button>
              </div>
            </div>

            {/* Steps */}
            <div className="card">
              <div className="card-header">
                <div className="card-title"><i className="fa fa-list-ol" /> Attack Steps</div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button className="btn btn-ghost" onClick={autoTimeline} style={{ fontSize: 10, padding: "4px 8px" }}
                    title="Auto-space steps evenly across duration">
                    <i className="fa fa-clock" /> Auto-time
                  </button>
                  <button className="btn btn-primary" onClick={() => addStep()} style={{ fontSize: 11, padding: "5px 10px" }}>
                    <i className="fa fa-plus" /> Step
                  </button>
                </div>
              </div>
              {steps.length === 0 && <div className="muted" style={{ fontSize: 12, padding: "16px 0", textAlign: "center" }}>
                Click a technique on the right to add steps, or click "+ Step" above
              </div>}
              {steps.map((s, i) => {
                const tech = techMap[s.technique];
                return (
                  <div key={s.id}
                    draggable onDragStart={() => setDragIdx(i)}
                    onDragOver={e => { e.preventDefault(); }}
                    onDrop={() => { if (dragIdx !== null) moveStep(dragIdx, i); setDragIdx(null); }}
                    style={{ display: "flex", gap: 8, padding: "10px 12px", marginBottom: 6, borderRadius: 8,
                      border: `1px solid ${s.is_inject ? "rgba(123,97,255,.3)" : "var(--gc-border)"}`,
                      background: s.is_inject ? "rgba(123,97,255,.04)" : "var(--gc-surface)",
                      alignItems: "flex-start", cursor: "grab" }}>
                    {/* Drag handle + number */}
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, minWidth: 28, paddingTop: 2 }}>
                      <i className="fa fa-grip-vertical" style={{ color: "var(--gc-muted)", fontSize: 10 }} />
                      <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--gc-accent)" }}>{i + 1}</span>
                      <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 4 }}>
                        <button onClick={() => moveStep(i, i - 1)} disabled={i === 0}
                          style={{ background: "none", border: "none", color: "var(--gc-muted)", cursor: "pointer", padding: 0, fontSize: 9 }}>
                          <i className="fa fa-chevron-up" />
                        </button>
                        <button onClick={() => moveStep(i, i + 1)} disabled={i === steps.length - 1}
                          style={{ background: "none", border: "none", color: "var(--gc-muted)", cursor: "pointer", padding: 0, fontSize: 9 }}>
                          <i className="fa fa-chevron-down" />
                        </button>
                      </div>
                    </div>

                    {/* Step content */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {/* Row 1: technique + phase + timing */}
                      <div style={{ display: "flex", gap: 6, marginBottom: 6, flexWrap: "wrap" }}>
                        <select className="form-select" value={s.technique} onChange={e => updateStep(i, { technique: e.target.value })}
                          style={{ flex: 2, minWidth: 160, fontSize: 12 }}>
                          <option value="">Select technique...</option>
                          {filteredTactics.map(tactic => (
                            <optgroup key={tactic} label={tactic}>
                              {techByTactic[tactic]?.map(t => (
                                <option key={t.key} value={t.key}>{t.mitre} {t.name}</option>
                              ))}
                            </optgroup>
                          ))}
                        </select>
                        <select className="form-select" value={s.phase} onChange={e => updateStep(i, { phase: e.target.value })}
                          style={{ width: 140, fontSize: 12 }}>
                          <option value="">Phase...</option>
                          {phases.map(p => <option key={p} value={p}>{p}</option>)}
                        </select>
                        <div style={{ display: "flex", alignItems: "center", gap: 3, minWidth: 70 }}>
                          <span style={{ fontSize: 10, color: "var(--gc-muted)" }}>T+</span>
                          <input className="form-input" type="number" value={s.at_min}
                            onChange={e => updateStep(i, { at_min: +e.target.value })} style={{ width: 50, fontSize: 12 }} />
                          <span style={{ fontSize: 10, color: "var(--gc-muted)" }}>min</span>
                        </div>
                      </div>

                      {/* Row 2: target + inject + label */}
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                        <select className="form-select" value={s.by} onChange={e => updateStep(i, { by: e.target.value })}
                          style={{ width: 70, fontSize: 11 }}>
                          <option value="type">type</option><option value="role">role</option>
                        </select>
                        <input className="form-input" value={s.value} onChange={e => updateStep(i, { value: e.target.value })}
                          placeholder="target..." style={{ width: 120, fontSize: 11 }} />
                        <button onClick={() => updateStep(i, { is_inject: !s.is_inject })}
                          className={"filter-chip" + (s.is_inject ? " active" : "")}
                          style={{ fontSize: 10, padding: "3px 8px", ...(s.is_inject ? { borderColor: "var(--gc-purple)", color: "var(--gc-purple)" } : {}) }}>
                          <i className="fa fa-bolt" /> inject
                        </button>
                        <input className="form-input" value={s.label} onChange={e => updateStep(i, { label: e.target.value })}
                          placeholder="custom label (optional)" style={{ flex: 1, minWidth: 100, fontSize: 11 }} />
                      </div>

                      {/* Tech info badge */}
                      {tech && (
                        <div style={{ display: "flex", gap: 6, marginTop: 6, alignItems: "center", flexWrap: "wrap" }}>
                          <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--gc-accent)" }}>{tech.mitre}</span>
                          <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 4, fontWeight: 600,
                            background: `${SEV_COLOR[tech.severity]}22`, color: SEV_COLOR[tech.severity] }}>{tech.severity}</span>
                          {tech.detects.map(d => <span key={d} className="tag" style={{ fontSize: 8 }}>{d}</span>)}
                          {tech.prevents.length > 0 && tech.prevents.map(p =>
                            <span key={p} style={{ fontSize: 9, color: "var(--gc-teal)" }}>blocked by {p}</span>
                          )}
                        </div>
                      )}

                      {/* Row 3: Fallback + Persistence (IRP ch.04/07) */}
                      <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap", alignItems: "center" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                          <span style={{ fontSize: 9, color: "var(--gc-muted)", whiteSpace: "nowrap" }}>fallback:</span>
                          <select className="form-select" value={s.fallback_technique}
                            onChange={e => updateStep(i, { fallback_technique: e.target.value })}
                            style={{ width: 160, fontSize: 11, padding: "3px 6px" }}>
                            <option value="">none</option>
                            {(techniques.data ?? []).filter(t => t.key !== s.technique).map(t => (
                              <option key={t.key} value={t.key}>{t.mitre} {t.name}</option>
                            ))}
                          </select>
                        </div>
                        {s.fallback_technique && <span style={{ fontSize: 9, color: "var(--gc-orange)", display: "flex", alignItems: "center", gap: 3 }}>
                          <i className="fa fa-code-branch" /> if blocked, pivots to {techMap[s.fallback_technique]?.name || s.fallback_technique}
                        </span>}
                        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                          <span style={{ fontSize: 9, color: "var(--gc-muted)", whiteSpace: "nowrap" }}>persistence:</span>
                          <select className="form-select" value={s.persistence_type}
                            onChange={e => updateStep(i, { persistence_type: e.target.value })}
                            style={{ width: 150, fontSize: 11, padding: "3px 6px" }}>
                            <option value="">none</option>
                            {PERSISTENCE_TYPES.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
                          </select>
                        </div>
                      </div>

                      {/* Row 4: Expected detections (IRP ch.02) */}
                      <div style={{ marginTop: 6 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                          <span style={{ fontSize: 9, color: "var(--gc-muted)" }}>expected detections ({(s.expected_detections ?? []).length})</span>
                          <button onClick={() => updateStep(i, { expected_detections: [...(s.expected_detections ?? []), { indicator_type: "Behavioural", signal: "", detection_source: "EDR", expected_priority: "P2" }] })}
                            style={{ background: "none", border: "none", color: "var(--gc-accent)", cursor: "pointer", fontSize: 9 }}>
                            <i className="fa fa-plus" /> add detection
                          </button>
                        </div>
                        {(s.expected_detections ?? []).map((det, di) => (
                          <div key={di} style={{ display: "flex", gap: 4, marginBottom: 3, alignItems: "center" }}>
                            <select className="form-select" value={det.indicator_type}
                              onChange={e => { const dets = [...(s.expected_detections ?? [])]; dets[di] = { ...dets[di], indicator_type: e.target.value }; updateStep(i, { expected_detections: dets }); }}
                              style={{ width: 90, fontSize: 10, padding: "2px 4px" }}>
                              {INDICATOR_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                            </select>
                            <input className="form-input" value={det.signal} placeholder="Signal description..."
                              onChange={e => { const dets = [...(s.expected_detections ?? [])]; dets[di] = { ...dets[di], signal: e.target.value }; updateStep(i, { expected_detections: dets }); }}
                              style={{ flex: 1, fontSize: 10, padding: "2px 6px" }} />
                            <select className="form-select" value={det.detection_source}
                              onChange={e => { const dets = [...(s.expected_detections ?? [])]; dets[di] = { ...dets[di], detection_source: e.target.value }; updateStep(i, { expected_detections: dets }); }}
                              style={{ width: 80, fontSize: 10, padding: "2px 4px" }}>
                              {DETECTION_SOURCES.map(s => <option key={s} value={s}>{s}</option>)}
                            </select>
                            <select className="form-select" value={det.expected_priority}
                              onChange={e => { const dets = [...(s.expected_detections ?? [])]; dets[di] = { ...dets[di], expected_priority: e.target.value }; updateStep(i, { expected_detections: dets }); }}
                              style={{ width: 48, fontSize: 10, padding: "2px 4px", color: det.expected_priority === "P0" ? "var(--gc-red)" : det.expected_priority === "P1" ? "var(--gc-orange)" : "var(--gc-muted)" }}>
                              {P_LEVELS.map(p => <option key={p} value={p}>{p}</option>)}
                            </select>
                            <button onClick={() => { const dets = (s.expected_detections ?? []).filter((_, j) => j !== di); updateStep(i, { expected_detections: dets }); }}
                              style={{ background: "none", border: "none", color: "var(--gc-muted)", cursor: "pointer", padding: 0, fontSize: 9 }}>
                              <i className="fa fa-times" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Delete */}
                    <button onClick={() => removeStep(i)}
                      style={{ background: "none", border: "none", color: "var(--gc-muted)", cursor: "pointer", padding: "4px", flexShrink: 0 }}>
                      <i className="fa fa-trash" style={{ fontSize: 12 }} />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: MITRE Technique Picker */}
          <div className="card" style={{ alignSelf: "flex-start", position: "sticky", top: 70, maxHeight: "calc(100vh - 90px)", overflowY: "auto" }}>
            <div className="card-title" style={{ marginBottom: 10 }}><i className="fa fa-crosshairs" /> MITRE ATT&CK Techniques</div>
            <input className="form-input" value={techFilter} onChange={e => setTechFilter(e.target.value)}
              placeholder="Search techniques..." style={{ marginBottom: 10, fontSize: 12 }} />
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 12 }}>
              <button className={"filter-chip" + (!tacticFilter ? " active" : "")} onClick={() => setTacticFilter("")}
                style={{ fontSize: 9, padding: "2px 6px" }}>All</button>
              {filteredTactics.map(t => (
                <button key={t} className={"filter-chip" + (tacticFilter === t ? " active" : "")}
                  onClick={() => setTacticFilter(tacticFilter === t ? "" : t)}
                  style={{ fontSize: 9, padding: "2px 6px" }}>{t.replace(" (ICS)", "")}</button>
              ))}
            </div>
            {filteredTactics.filter(t => !tacticFilter || t === tacticFilter).map(tactic => {
              const techs = (techByTactic[tactic] || []).filter(t =>
                !techFilter || t.name.toLowerCase().includes(techFilter.toLowerCase()) || t.mitre.toLowerCase().includes(techFilter.toLowerCase())
              );
              if (techs.length === 0) return null;
              return (
                <div key={tactic} style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, color: "var(--gc-muted)", marginBottom: 6 }}>{tactic}</div>
                  {techs.map(t => {
                    const used = steps.filter(s => s.technique === t.key).length;
                    return (
                      <div key={t.key} onClick={() => addStep(t.key, t.tactic)}
                        style={{ display: "flex", gap: 8, padding: "7px 10px", borderRadius: 6, marginBottom: 3,
                          border: "1px solid var(--gc-border)", cursor: "pointer", transition: "all .15s",
                          background: used > 0 ? "rgba(0,212,255,.04)" : "transparent" }}
                        onMouseEnter={e => (e.currentTarget.style.borderColor = "var(--gc-accent)")}
                        onMouseLeave={e => (e.currentTarget.style.borderColor = "var(--gc-border)")}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 12, fontWeight: 600, display: "flex", gap: 6, alignItems: "center" }}>
                            <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--gc-accent)" }}>{t.mitre}</span>
                            {t.name}
                            {used > 0 && <span style={{ fontFamily: "var(--mono)", fontSize: 9, color: "var(--gc-teal)", background: "rgba(0,212,255,.1)", padding: "1px 5px", borderRadius: 3 }}>{used}x</span>}
                          </div>
                          <div style={{ fontSize: 10, color: "var(--gc-muted)", marginTop: 1 }}>{t.description}</div>
                        </div>
                        <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 4, fontWeight: 600, alignSelf: "flex-start",
                          background: `${SEV_COLOR[t.severity]}22`, color: SEV_COLOR[t.severity] }}>{t.severity}</span>
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB: Environment */}
      {activeTab === "environment" && (
        <div className="grid-2">
          <div>
            {/* Asset Topology */}
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header">
                <div className="card-title"><i className="fa fa-server" /> Assets ({pickedAssets.length})</div>
              </div>
              {/* Assets grouped by zone */}
              {ZONES.map(zone => {
                const zoneAssets = pickedAssets.filter(a => a.zone === zone);
                if (zoneAssets.length === 0 && !["corp", "perimeter"].includes(zone)) return null;
                return (
                  <div key={zone} style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1.5, color: "var(--gc-muted)", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--gc-accent)", flexShrink: 0 }} />
                      {ZONE_LABEL[zone]} zone ({zoneAssets.length})
                    </div>
                    {zoneAssets.map(a => (
                      <div key={a.id} style={{ display: "flex", gap: 8, alignItems: "center", padding: "8px 10px", marginBottom: 4,
                        borderRadius: 8, border: "1px solid var(--gc-border)", background: "var(--gc-surface)" }}>
                        <i className={`fa ${assetCatMap[a.type]?.icon || "fa-server"}`} style={{ color: "var(--gc-accent)", width: 20, textAlign: "center" }} />
                        <input className="form-input" value={a.name} onChange={e => updateAsset(a.id, { name: e.target.value })}
                          style={{ flex: 1, fontSize: 12, padding: "4px 8px" }} />
                        <select className="form-select" value={a.zone} onChange={e => updateAsset(a.id, { zone: e.target.value })}
                          style={{ width: 90, fontSize: 11, padding: "4px 6px" }}>
                          {ZONES.map(z => <option key={z} value={z}>{ZONE_LABEL[z]}</option>)}
                        </select>
                        <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
                          <span style={{ fontSize: 9, color: "var(--gc-muted)" }}>crit</span>
                          <input className="form-input" type="number" min={1} max={5} value={a.criticality}
                            onChange={e => updateAsset(a.id, { criticality: +e.target.value })}
                            style={{ width: 40, fontSize: 11, padding: "4px 6px", textAlign: "center" }} />
                        </div>
                        <button onClick={() => removeAsset(a.id)}
                          style={{ background: "none", border: "none", color: "var(--gc-muted)", cursor: "pointer" }}>
                          <i className="fa fa-times" style={{ fontSize: 11 }} />
                        </button>
                      </div>
                    ))}
                  </div>
                );
              })}

              {/* Add asset */}
              <div style={{ marginTop: 10 }}>
                <div className="builder-label">Add asset</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                  {(assets.data ?? []).map(a => (
                    <div key={a.key} className="asset-tile" onClick={() => addAsset(a.key)} style={{ padding: "8px 10px" }}>
                      <div className="icon" style={{ width: 24, height: 24, fontSize: 12 }}><i className={`fa ${a.icon}`} /></div>
                      <div style={{ fontSize: 11 }}>{a.name}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div>
            {/* Controls */}
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-title" style={{ marginBottom: 10 }}><i className="fa fa-shield-alt" /> Controls</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {(controls.data ?? []).map(c => (
                  <button key={c.key} className={"filter-chip" + (pickedControls.has(c.key) ? " active" : "")}
                    onClick={() => toggleControl(c.key)} style={{ fontSize: 12 }}>
                    <i className={`fa ${c.icon}`} /> {c.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Workflow Bindings */}
            <div className="card">
              <div className="card-title" style={{ marginBottom: 10 }}><i className="fa fa-list-check" /> Workflow Bindings</div>
              <div style={{ fontSize: 11, color: "var(--gc-muted)", marginBottom: 10 }}>
                Which team workflows are bound to this scenario. These reference the reusable IRP-based workflow catalog.
              </div>
              {["red", "soc", "blue", "mgmt", "ot"].map(actor => {
                const available = (workflows.data ?? []).filter(w => w.actor === actor);
                return (
                  <div key={actor} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
                    <span style={{ fontFamily: "var(--mono)", fontSize: 11, fontWeight: 600, minWidth: 40,
                      textTransform: "uppercase", color: actor === "red" ? "var(--gc-red)" : actor === "blue" ? "#5B8CFF" : actor === "soc" ? "var(--gc-green)" : "var(--gc-muted)" }}>
                      {actor}
                    </span>
                    <select className="form-select" value={wfBindings[actor] || ""} onChange={e => setWfBindings(prev => ({ ...prev, [actor]: e.target.value }))}
                      style={{ flex: 1, fontSize: 12 }}>
                      {available.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
                    </select>
                  </div>
                );
              })}
            </div>

            {/* Decision Gates (IRP ch.03) */}
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-title" style={{ marginBottom: 6 }}><i className="fa fa-code-branch" /> Decision Gates (IRP ch.03)</div>
              <div style={{ fontSize: 11, color: "var(--gc-muted)", marginBottom: 12 }}>
                Containment IF/THEN branches the engine enforces. Each gate scores Blue on whether they followed correct procedure.
              </div>
              {DECISION_GATES.map(g => {
                const on = decisionGates.has(g.id);
                return (
                  <div key={g.id} onClick={() => setDecisionGates(prev => {
                    const n = new Set(prev); n.has(g.id) ? n.delete(g.id) : n.add(g.id); return n;
                  })} style={{ display: "flex", gap: 10, padding: "10px 12px", marginBottom: 6, borderRadius: 8,
                    border: `1px solid ${on ? "rgba(0,212,255,.3)" : "var(--gc-border)"}`,
                    background: on ? "rgba(0,212,255,.04)" : "var(--gc-surface)", cursor: "pointer", opacity: on ? 1 : 0.55 }}>
                    <i className={`fa ${on ? "fa-check-square" : "fa-square"}`}
                      style={{ color: on ? "var(--gc-accent)" : "var(--gc-muted)", fontSize: 14, marginTop: 2 }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                        {g.name}
                        <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 4, fontWeight: 600,
                          background: `${RISK_COLOR[g.risk]}22`, color: RISK_COLOR[g.risk] }}>{g.risk} risk</span>
                      </div>
                      <div style={{ fontSize: 10, color: "var(--gc-muted)", marginTop: 2 }}>{g.desc}</div>
                      <div style={{ fontSize: 9, color: "var(--gc-muted)", marginTop: 2, fontFamily: "var(--mono)" }}>{g.irp} · trigger: {g.trigger}</div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Regulatory Frameworks (IRP ch.12) */}
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-header">
                <div className="card-title"><i className="fa fa-gavel" /> Regulatory Frameworks (IRP ch.12)</div>
                <button className="btn btn-ghost" style={{ fontSize: 9, padding: "3px 8px" }}
                  onClick={() => setRegFrameworks(new Set(suggestedFrameworks))}>
                  <i className="fa fa-wand-magic-sparkles" /> auto ({industry})
                </button>
              </div>
              <div style={{ fontSize: 11, color: "var(--gc-muted)", marginBottom: 10 }}>
                Which notification obligations apply. The engine tracks whether Management meets each deadline and scores accordingly.
              </div>
              {REG_FRAMEWORKS.map(fw => {
                const on = regFrameworks.has(fw.id);
                const suggested = suggestedFrameworks.includes(fw.id);
                return (
                  <div key={fw.id} onClick={() => setRegFrameworks(prev => {
                    const n = new Set(prev); n.has(fw.id) ? n.delete(fw.id) : n.add(fw.id); return n;
                  })} style={{ display: "flex", gap: 10, padding: "10px 12px", marginBottom: 6, borderRadius: 8,
                    border: `1px solid ${on ? "rgba(255,214,0,.3)" : "var(--gc-border)"}`,
                    background: on ? "rgba(255,214,0,.04)" : "var(--gc-surface)", cursor: "pointer", opacity: on ? 1 : 0.5 }}>
                    <i className={`fa ${on ? "fa-check-square" : "fa-square"}`}
                      style={{ color: on ? "var(--gc-yellow)" : "var(--gc-muted)", fontSize: 14, marginTop: 2 }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                        {fw.name}
                        <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 4, background: "rgba(255,255,255,.06)", color: "var(--gc-muted)" }}>{fw.jurisdiction}</span>
                        {suggested && <span style={{ fontSize: 8, padding: "1px 5px", borderRadius: 3, background: "rgba(0,212,255,.1)", color: "var(--gc-accent)" }}>suggested</span>}
                      </div>
                      <div style={{ display: "flex", gap: 12, fontSize: 10, color: "var(--gc-muted)", marginTop: 4 }}>
                        <span><i className="fa fa-clock" style={{ marginRight: 3 }} />{fw.deadline}</span>
                        <span><i className="fa fa-exclamation-triangle" style={{ marginRight: 3, color: "var(--gc-red)" }} />{fw.penalty}</span>
                        <span style={{ fontFamily: "var(--mono)" }}>trigger: {fw.trigger}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* TAB: Objectives */}
      {activeTab === "objectives" && (
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}><i className="fa fa-bullseye" /> Team Objectives (one per line)</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {[
              { key: "red", label: "Red Team", color: "var(--gc-red)", icon: "fa-crosshairs", placeholder: "Achieve initial access via phishing\nEscalate to Domain Admin\nExfiltrate sensitive data\nDeploy ransomware" },
              { key: "soc", label: "SOC", color: "var(--gc-green)", icon: "fa-eye", placeholder: "Detect initial access within 5 minutes\nCorrectly classify severity level\nEscalate to IR within 10 minutes\nIdentify all compromised hosts" },
              { key: "blue", label: "Blue Team", color: "#5B8CFF", icon: "fa-shield-alt", placeholder: "Contain compromised hosts\nPreserve memory evidence before isolation\nReset all compromised credentials\nRestore from clean backups" },
              { key: "mgmt", label: "Management", color: "var(--gc-accent2)", icon: "fa-briefcase", placeholder: "Notify CISO within 30 minutes of P1\nDeclare P0 on domain breach\nEngage Legal for regulatory assessment" },
              { key: "ot", label: "OT / Operations", color: "var(--gc-orange)", icon: "fa-industry", placeholder: "Switch to manual operations\nProtect safety interlocks\nIsolate OT segment" },
            ].map(({ key, label, color, icon, placeholder }) => (
              <div key={key}>
                <div style={{ fontSize: 12, fontWeight: 700, color, marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                  <i className={`fa ${icon}`} /> {label}
                </div>
                <textarea className="form-textarea" value={objectives[key]} onChange={e => setObjectives(prev => ({ ...prev, [key]: e.target.value }))}
                  placeholder={placeholder} style={{ minHeight: 100, fontSize: 12 }} />
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
