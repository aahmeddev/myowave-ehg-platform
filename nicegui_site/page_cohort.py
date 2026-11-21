import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from nicegui import ui, run
from config_db import init_firebase
from layout import frame

db_cloud = init_firebase()

# Global Memory Cache
# Stores calculated data and Plotly objects directly in server memory for performance.
COHORT_VAULT = {}


def clear_cohort_vault():
    """Clear the cohort memory cache to allow for a fresh data load. Invoke upon data modification."""
    print("Clearing Cohort RAM Vault for fresh data load...")
    COHORT_VAULT.clear()


def fetch_all_events():
    """Retrieve events from Firebase, using the in-memory cache if available."""
    if 'raw_df' in COHORT_VAULT:
        return COHORT_VAULT['raw_df']

    print("Live Data Load: Reading events from Firebase...")
    events_data = []
    events = db_cloud.collection_group('events').stream()
    for ev in events:
        events_data.append(ev.to_dict())

    df = pd.DataFrame(events_data)
    COHORT_VAULT['raw_df'] = df
    return df


def generate_plots():
    """Generate Plotly visualisation objects or retrieve them from the cache."""

    # 1. Evaluate cache availability.
    if 'plots' in COHORT_VAULT:
        return COHORT_VAULT['plots']

    # 2. Perform calculations if the cache is unpopulated.
    df = fetch_all_events()

    if df.empty:
        return 0, None, None, None

    df_clean = df[df['dominant_freq_hz'] > 0.0].copy()
    df_clean = df_clean.dropna(subset=['rms_v', 'dominant_freq_hz', 'burst_duration_sec', 'max_amplitude_v'])

    if df_clean.empty:
        return 0, None, None, None

    if 'pain_scale' not in df_clean.columns: df_clean['pain_scale'] = 0.0
    df_clean['pain_scale'] = df_clean['pain_scale'].fillna(0.0)

    if 'diagnosis' not in df_clean.columns: df_clean['diagnosis'] = 'Unknown'
    df_clean['diagnosis'] = df_clean['diagnosis'].fillna('Unknown')

    if 'cycle_day' not in df_clean.columns: df_clean['cycle_day'] = 0
    df_clean['cycle_day'] = df_clean['cycle_day'].fillna(0)

    # Construct the summary table.
    pt_summary = df_clean.groupby('patient_id').agg({
        'event_id': 'count',
        'diagnosis': 'first',
        'pain_scale': 'max',
        'rms_v': 'mean',
        'dominant_freq_hz': 'mean'
    }).reset_index()

    pt_summary.rename(columns={'event_id': 'Total Events', 'rms_v': 'Avg Intensity', 'dominant_freq_hz': 'Avg Freq'},
                      inplace=True)
    pt_summary['Avg Intensity'] = pt_summary['Avg Intensity'].round(4)
    pt_summary['Avg Freq'] = pt_summary['Avg Freq'].round(3)

    # Construct the violin plots.
    df_viz = df_clean.copy()
    for col in ['rms_v', 'dominant_freq_hz', 'burst_duration_sec', 'max_amplitude_v']:
        upper_limit = df_viz[col].quantile(0.99)
        df_viz = df_viz[df_viz[col] <= upper_limit]

    fig_violins = make_subplots(rows=2, cols=2,
                                subplot_titles=("RMS Intensity (V)", "Dominant Frequency (Hz)", "Burst Duration (s)",
                                                "Max Amplitude (V)"), vertical_spacing=0.15, horizontal_spacing=0.1)

    df_violins = df_viz[df_viz['diagnosis'] != 'Unknown']
    diagnoses = df_violins['diagnosis'].unique()
    colors = px.colors.qualitative.Bold
    metrics = [('rms_v', 1, 1), ('dominant_freq_hz', 1, 2), ('burst_duration_sec', 2, 1), ('max_amplitude_v', 2, 2)]

    for idx, diag in enumerate(diagnoses):
        df_diag = df_violins[df_violins['diagnosis'] == diag]
        color = colors[idx % len(colors)]
        for metric, row, col in metrics:
            fig_violins.add_trace(
                go.Violin(y=df_diag[metric], name=diag, line_color=color, box_visible=False, meanline_visible=True,
                          points=False, scalemode='width', width=0.8, showlegend=(row == 1 and col == 1)), row=row,
                col=col)

    fig_violins.update_layout(height=800, margin=dict(l=20, r=20, t=40, b=20), plot_bgcolor='rgba(248, 250, 252, 1)',
                              paper_bgcolor='rgba(255, 255, 255, 0)', violinmode='group')

    # Construct the diagnostic density heatmap.
    df_cluster = df_clean[df_clean['diagnosis'] != 'Unknown'].copy()

    freq_upper = df_cluster['dominant_freq_hz'].quantile(0.99) * 1.2
    rms_upper = df_cluster['rms_v'].quantile(0.99) * 1.2

    fig_cluster = px.density_heatmap(
        df_cluster,
        x="dominant_freq_hz",
        y="rms_v",
        facet_col="diagnosis",
        category_orders={"diagnosis": ["Healthy", "Endometriosis", "Dysmenorrhea", "Adenomyosis"]},
        color_continuous_scale=px.colors.sequential.Viridis,
        labels={"dominant_freq_hz": "Frequency (Hz)", "rms_v": "RMS Power (V)", "diagnosis": "Cohort"}
    )

    fig_cluster.update_layout(margin=dict(l=20, r=20, t=40, b=20), plot_bgcolor='rgba(248, 250, 252, 1)',
                              paper_bgcolor='rgba(255, 255, 255, 0)')
    fig_cluster.update_xaxes(range=[0, freq_upper])
    fig_cluster.update_yaxes(range=[0, rms_upper])

    # 3. Cache the generated plots before returning.
    COHORT_VAULT['plots'] = (len(df_clean), pt_summary, fig_violins, fig_cluster)
    return COHORT_VAULT['plots']


def render_cohort():
    """Main user interface rendering function. Utilizes memory cache for rapid loading."""
    frame('/cohort')
    ui.label("Clinical Cohort Analysis").classes('text-2xl font-semibold mb-6 text-slate-800 tracking-tight')

    content_container = ui.column().classes('w-full')

    async def load_dashboard():
        with content_container:
            # Display a loading indicator if the cache is empty.
            spinner = None
            if 'plots' not in COHORT_VAULT:
                spinner = ui.spinner('dots', size='lg').classes('mt-10 mx-auto text-slate-400')

            # Asynchronously fetch plot data.
            total_events, pt_summary, fig_violins, fig_cluster = await run.io_bound(generate_plots)

            if spinner:
                content_container.remove(spinner)

            if total_events == 0:
                ui.label("No valid physiological events available for cohort analysis.").classes('text-slate-500')
                return

            with ui.row().classes('w-full mb-8'):
                with ui.card().classes('p-6 shadow-sm border border-slate-200 border-l-4 border-l-slate-800 w-1/4'):
                    ui.label("Total Global Contractions").classes('text-xs text-slate-500 uppercase tracking-widest')
                    ui.label(str(total_events)).classes('text-3xl font-semibold text-slate-800 mt-2')

            ui.label("Patient Cohort Summary").classes('text-lg font-medium mb-4 text-slate-700 border-b pb-2')
            ui.aggrid.from_pandas(pt_summary).classes('h-64 w-full mb-10 shadow-sm border border-slate-200')

            ui.label("Morphological Density Profiles").classes(
                'text-lg font-medium mb-2 text-slate-700 border-b pb-2 w-full')
            ui.label("Violin plots with mathematically significant outliers. Extreme 1% artifacts filtered.").classes(
                'text-sm text-slate-500 mb-4')
            with ui.card().classes('w-full p-4 shadow-sm border border-slate-200 mb-10'):
                ui.plotly(fig_violins).classes('w-full')

            with ui.row().classes('w-full gap-8 mb-10'):
                with ui.column().classes('w-full flex-grow'):
                    ui.label("Diagnostic Density Clustering").classes(
                        'text-lg font-medium mb-2 text-slate-700 border-b pb-2 w-full')
                    ui.label("2D Histogram revealing high-concentration clinical feature signatures.").classes(
                        'text-sm text-slate-500 mb-4')
                    with ui.card().classes('w-full p-4 shadow-sm border border-slate-200 h-96'):
                        ui.plotly(fig_cluster).classes('w-full h-full')

    ui.timer(0, load_dashboard, once=True)