"""
page_export.py
MYOWAVE EHG Biosensor Platform
Data Export Manager component.
"""

import os
import csv
import io
import pandas as pd
from nicegui import ui
from config_db import init_firebase
from layout import frame

db_cloud = init_firebase()

# Badge Configuration Metadata
_DIAG_CONFIG = {
    "Healthy":       {"badge": "Control",     "badgeBg": "#E1F5EE", "badgeColor": "#085041"},
    "Endometriosis": {"badge": "Stage II-IV", "badgeBg": "#FAECE7", "badgeColor": "#4A1B0C"},
    "Dysmenorrhea":  {"badge": "Primary",     "badgeBg": "#FAEEDA", "badgeColor": "#412402"},
    "Adenomyosis":   {"badge": "Confirmed",   "badgeBg": "#EEEDFE", "badgeColor": "#26215C"},
    "_default":      {"badge": "",            "badgeBg": "#F1EFE8", "badgeColor": "#5F5E5A"},
}

_EXPORT_COLUMNS = [
    "diagnosis", "patient_id", "session_id", "event_id",
    "timestamp_start", "rms_v", "max_amplitude_v", "burst_duration_sec",
    "ibi_sec", "dominant_freq_hz", "power_fwh", "power_fwl",
]

# Data Layer Operations

def _fetch_events() -> pd.DataFrame:
    if os.path.exists("synthetic_cohort_data.csv"):
        return pd.read_csv("synthetic_cohort_data.csv")

    events_data = []
    for doc in db_cloud.collection_group("events").stream():
        events_data.append(doc.to_dict())
    return pd.DataFrame(events_data)

def _build_hierarchy(df: pd.DataFrame) -> dict:
    df = df.copy()

    if "diagnosis" not in df.columns:
        diag_map = {"HE": "Healthy", "EN": "Endometriosis",
                    "DY": "Dysmenorrhea", "AD": "Adenomyosis"}
        df["diagnosis"] = df["patient_id"].str[:2].map(diag_map).fillna("Unknown")

    if "timestamp_start" in df.columns:
        df["_ts_display"] = (
            pd.to_datetime(df["timestamp_start"], unit="s", errors="coerce")
            .dt.strftime("%Y-%m-%d %H:%M")
            .fillna("-")
        )
    else:
        df["_ts_display"] = "-"

    if "burst_duration_sec" in df.columns:
        df["_dur_display"] = df["burst_duration_sec"].apply(
            lambda x: f"{int(round(x))}s" if pd.notna(x) else "-"
        )
    else:
        df["_dur_display"] = "-"

    df["rms_v"]            = pd.to_numeric(df.get("rms_v"),            errors="coerce").fillna(0.0)
    df["dominant_freq_hz"] = pd.to_numeric(df.get("dominant_freq_hz"), errors="coerce").fillna(0.0)

    hierarchy: dict = {}
    for diag, g_diag in df.groupby("diagnosis"):
        cfg = _DIAG_CONFIG.get(diag, _DIAG_CONFIG["_default"])
        hierarchy[diag] = {
            "_badge":      cfg["badge"],
            "_badgeBg":    cfg["badgeBg"],
            "_badgeColor": cfg["badgeColor"],
            "patients":    {},
        }
        for pat, g_pat in g_diag.groupby("patient_id"):
            events = []
            for _, row in g_pat.iterrows():
                row_dict = {}
                for col in _EXPORT_COLUMNS:
                    val = row.get(col, None)
                    row_dict[col] = "" if (pd.isna(val) if not isinstance(val, str) else False) else val
                events.append({
                    "event_id":   str(row.get("event_id", "-")),
                    "session_id": str(row.get("session_id", "-")),
                    "ts":         row["_ts_display"],
                    "dur":        row["_dur_display"],
                    "rms":        round(float(row["rms_v"]), 4),
                    "freq":       round(float(row["dominant_freq_hz"]), 3),
                    "row":        row_dict,
                })
            hierarchy[diag]["patients"][pat] = events
    return hierarchy

# Page Rendering Operations

class ExportState:
    def __init__(self, hierarchy: dict):
        self.hierarchy = hierarchy
        self.diag_open: dict[str, bool] = {}
        self.pat_open: dict[str, bool] = {}
        self.ev_checked: dict[str, bool] = {}

    def all_ev_ids(self, diag: str) -> list:
        return [e["event_id"] for events in self.hierarchy[diag]["patients"].values() for e in events]

    def pat_ev_ids(self, diag: str, pat: str) -> list:
        return [e["event_id"] for e in self.hierarchy[diag]["patients"][pat]]

    def set_evs(self, ids: list, val: bool):
        for ev_id in ids: self.ev_checked[ev_id] = val

    def diag_state(self, diag: str) -> str:
        ids = self.all_ev_ids(diag)
        n = sum(1 for ev_id in ids if self.ev_checked.get(ev_id, False))
        if n == 0: return "none"
        return "all" if n == len(ids) else "some"

    def pat_state(self, diag: str, pat: str) -> str:
        ids = self.pat_ev_ids(diag, pat)
        n = sum(1 for ev_id in ids if self.ev_checked.get(ev_id, False))
        if n == 0: return "none"
        return "all" if n == len(ids) else "some"

    def get_selected_events(self) -> list:
        selected = []
        for diag, group in self.hierarchy.items():
            for pat, events in group["patients"].items():
                for ev in events:
                    if self.ev_checked.get(ev["event_id"], False):
                        row = dict(ev["row"])
                        row["diagnosis"] = diag
                        row["patient_id"] = pat
                        selected.append(row)
        return selected

    def total_events(self) -> int:
        return sum(len(events) for group in self.hierarchy.values() for events in group["patients"].values())

    def clear_all(self): self.ev_checked.clear()

def render_export() -> None:
    frame("/export")

    # 1. Configure the parent container for vertical screen filling.
    with ui.column().classes("px-6 py-6 w-full h-[calc(100vh-80px)] flex-nowrap"):

        # 2. Prevent title compression using flex-shrink settings.
        ui.label("Data Export Manager").classes("text-2xl font-semibold text-slate-800 tracking-tight flex-shrink-0")
        ui.label("Select events by diagnosis group, patient, or individual recording.").classes("text-sm text-slate-500 mt-1 mb-6 flex-shrink-0")

        try:
            df = _fetch_events()
        except Exception as exc:
            ui.label(f"Failed to load data: {exc}").classes("text-red-500 italic")
            return

        hierarchy = _build_hierarchy(df)
        state = ExportState(hierarchy)

        # 3. Implement flex-grow to allow automatic vertical stretching.
        with ui.card().classes("w-full flex-grow flex flex-row overflow-hidden border border-slate-200 rounded-xl shadow-sm bg-white"):
            with ui.column().classes("flex-1 overflow-hidden h-full"):
                with ui.row().classes("items-center gap-2 p-3 border-b bg-slate-50 w-full flex-shrink-0"):
                    ui.icon("database").classes("text-slate-500")
                    ui.label("Event Explorer").classes("text-sm font-medium text-slate-700 flex-1")
                    ui.button(icon="unfold_more", on_click=lambda: (expand_all(), render_tree.refresh(), update_stats())).props("flat size=sm")
                    ui.button(icon="unfold_less", on_click=lambda: (collapse_all(), render_tree.refresh(), update_stats())).props("flat size=sm")
                    ui.button(icon="clear", on_click=lambda: (state.clear_all(), render_tree.refresh(), update_stats())).props("flat size=sm")

                tree_container = ui.column().classes("flex-1 overflow-y-auto w-full p-2")

            with ui.column().classes("w-64 border-l bg-slate-50 h-full p-4 flex-shrink-0"):
                ui.label("SELECTION").classes("text-xs font-bold tracking-wider text-slate-400 mb-4")
                selected_events_label = ui.label("0").classes("text-3xl font-bold text-emerald-800")
                ui.label("events selected").classes("text-xs text-slate-500")
                with ui.element("div").classes("w-full bg-slate-200 h-1.5 rounded-full overflow-hidden my-4"):
                    progress_bar = ui.element("div").classes("bg-emerald-600 h-full transition-all").style("width: 0%")
                selected_pats_label = ui.label("0").classes("text-xl font-semibold")
                ui.label("patients").classes("text-xs text-slate-500 mb-3")
                selected_groups_label = ui.label("0").classes("text-xl font-semibold")
                ui.label("diagnosis groups").classes("text-xs text-slate-500 mb-3")
                size_label = ui.label("0 KB").classes("text-xl font-semibold")
                ui.label("estimated size").classes("text-xs text-slate-500")
                with ui.column().classes("w-full mt-auto gap-2"):
                    csv_btn = ui.button("Export CSV", icon="download", on_click=lambda: export_csv(state)).classes("w-full bg-emerald-700").props("no-caps")
                    edf_btn = ui.button("Export EDF+", icon="waveform", on_click=lambda: export_edf(state)).classes("w-full").props("flat no-caps")
                    csv_btn.set_enabled(False)
                    edf_btn.set_enabled(False)

            def expand_all():
                for d in state.hierarchy:
                    state.diag_open[d] = True
                    for p in state.hierarchy[d]["patients"]: state.pat_open[f"{d}|{p}"] = True

            def collapse_all():
                for d in state.hierarchy: state.diag_open[d] = False
                state.pat_open.clear()

            @ui.refreshable
            def render_tree():
                tree_container.clear()
                with tree_container:
                    for diag in state.hierarchy:
                        group = state.hierarchy[diag]
                        cfg = _DIAG_CONFIG.get(diag, _DIAG_CONFIG["_default"])
                        is_open = state.diag_open.get(diag, False)
                        ds = state.diag_state(diag)

                        # Render group row elements.
                        with ui.row().classes("items-center p-1 cursor-pointer hover:bg-emerald-50 w-full"):
                            ui.icon("chevron_right" if not is_open else "expand_more").classes("text-slate-400 cursor-pointer").on("click", lambda d=diag: (state.diag_open.update({d: not state.diag_open.get(d, False)}), render_tree.refresh()))

                            cb = ui.checkbox(value=(ds == "all")).props("dense")
                            if ds == "some": cb.props("indeterminate")
                            cb.on("click", lambda d=diag: (state.set_evs(state.all_ev_ids(d), state.diag_state(d) != "all"), render_tree.refresh(), update_stats()))

                            ui.label(diag).classes("text-sm font-medium flex-1 pl-2")
                            ui.label(f"{len(group['patients'])}pt - {len(state.all_ev_ids(diag))}ev").classes("text-xs text-slate-400")

                        if is_open:
                            for pat in group["patients"]:
                                pat_key = f"{diag}|{pat}"
                                po = state.pat_open.get(pat_key, False)
                                ps = state.pat_state(diag, pat)

                                with ui.row().classes("items-center p-1 pl-8 hover:bg-emerald-50 w-full"):
                                    ui.icon("chevron_right" if not po else "expand_more").classes("text-slate-400 cursor-pointer").on("click", lambda d=diag, p=pat: (state.pat_open.update({f"{d}|{p}": not state.pat_open.get(f"{d}|{p}", False)}), render_tree.refresh()))

                                    pcb = ui.checkbox(value=(ps == "all")).props("dense")
                                    if ps == "some": pcb.props("indeterminate")
                                    pcb.on("click", lambda d=diag, p=pat: (state.set_evs(state.pat_ev_ids(d, p), state.pat_state(d, p) != "all"), render_tree.refresh(), update_stats()))

                                    ui.icon("person").classes("text-sm text-slate-400")
                                    ui.label(pat).classes("text-sm flex-1")
                                    ui.label(f"{len(group['patients'][pat])} events").classes("text-xs text-slate-400")

                                if po:
                                    for ev in group["patients"][pat]:
                                        with ui.row().classes("items-center p-1 pl-16 hover:bg-emerald-50 w-full"):
                                            ui.checkbox(value=state.ev_checked.get(ev["event_id"], False)).props("dense").on("click", lambda ev_id=ev["event_id"]: (state.ev_checked.update({ev_id: not state.ev_checked.get(ev_id, False)}), render_tree.refresh(), update_stats()))
                                            ui.label(ev["event_id"]).classes("text-xs flex-1 pl-6")
                                            ui.label(f"{ev['ts']} - {ev['rms']} RMS").classes("text-xs text-slate-400")

            def update_stats():
                selected = state.get_selected_events()
                sel_count = len(selected)
                sel_pats = {r["patient_id"] for r in selected}
                sel_groups = {r["diagnosis"] for r in selected}
                selected_events_label.set_text(str(sel_count))
                selected_pats_label.set_text(str(len(sel_pats)))
                selected_groups_label.set_text(str(len(sel_groups)))
                size_label.set_text(f"{sel_count * 2.4:.1f} KB")
                total = state.total_events()
                pct = round(sel_count / total * 100) if total > 0 else 0
                progress_bar.style(f"width: {pct}%")
                csv_btn.set_enabled(sel_count > 0)
                edf_btn.set_enabled(sel_count > 0)

            def export_csv(state: ExportState):
                selected = state.get_selected_events()
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=_EXPORT_COLUMNS)
                writer.writeheader()
                for row in selected: writer.writerow({col: row.get(col, "") for col in _EXPORT_COLUMNS})
                ui.download(output.getvalue().encode("utf-8"), f"export_{len(selected)}events.csv", "text/csv")

            def export_edf(state: ExportState):
                pass

            render_tree()
            update_stats()