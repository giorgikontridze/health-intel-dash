import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import folium
from folium.plugins import HeatMap
import numpy as np
import io
import os

# --- 1. STATIC DATA ---
hosp_data = {
    'Hospital_ID': ['H1', 'H2', 'H3', 'H4', 'H5'],
    'Name': ['Downtown Clinic', 'East Hub', 'West Medical', 'South Center', 'North Health'],
    'Latitude': [38.2527, 38.2450, 38.2600, 38.1800, 38.3200],
    'Longitude': [-85.7585, -85.6000, -85.8500, -85.7500, -85.7000]
}
hosp = pd.DataFrame(hosp_data)

def haversine(lat1, lon1, lat2, lon2):
    try:
        R = 3958.8
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
        return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return 999.0

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# --- 2. CSS FORCING (მკაცრი შეზღუდვა) ---
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Health Intel Pro</title>
        {%favicon%}
        {%css%}
        <style>
            html, body { 
                margin: 0 !important; 
                padding: 0 !important; 
                height: 100vh !important; 
                width: 100vw !important;
                overflow: hidden !important; /* აქ ითიშება ჩამოსქროლვა */
                position: fixed !important; 
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# --- 3. LAYOUT ---
app.layout = html.Div([
    # რუკა - იკავებს ზუსტად ეკრანის ზომას და არსად არ იძვრება
    html.Iframe(
        id='map-display', 
        style={
            'position': 'fixed',
            'top': 0,
            'left': 0,
            'width': '100vw', 
            'height': '100vh', 
            'border': 'none',
            'display': 'block',
            'z-index': '1'
        }
    ),

    # Sidebar - დაცურავს რუკის ზემოთ
    html.Div([
        html.H3("🏥 Health Intel Pro", style={'fontWeight': '800', 'color': '#1e293b'}),
        html.Div(id='analysis-output'),
        html.Hr(),
        html.Label("Service Radius (Miles)", className="fw-bold small"),
        dcc.Slider(id='radius-slider', min=1, max=20, step=1, value=5, 
                   marks={i: str(i) for i in [1, 5, 10, 15, 20]}, className="mb-4"),
        html.Label("Heatmap Intensity", className="fw-bold small"),
        dcc.Slider(id='heat-slider', min=0.1, max=1.0, step=0.1, value=0.5, className="mb-4"),
        dbc.Checklist(
            options=[{"label": "Show ONLY Gap Patients", "value": 1}],
            value=[], id="filter-switch", switch=True, className="mb-4 small fw-bold"
        ),
        dbc.Button("📊 Download Report", id="btn-excel", color="danger", className="w-100"),
        dcc.Download(id="download-excel")
    ], style={
        "position": "fixed", 
        "top": "20px", 
        "left": "20px", 
        "width": "320px",
        "background-color": "rgba(255, 255, 255, 0.95)", 
        "padding": "25px",
        "border-radius": "16px", 
        "box-shadow": "0 12px 40px rgba(0,0,0,0.3)", 
        "z-index": "1000", 
        "maxHeight": "calc(100vh - 40px)", 
        "overflowY": "auto" # სქროლი მხოლოდ მენიუს ექნება თუ არ დაეტევა
    })
], style={'height': '100vh', 'width': '100vw', 'overflow': 'hidden'})

# --- 4. CALLBACKS ---
@app.callback(
    [Output('map-display', 'srcDoc'), Output('analysis-output', 'children')],
    [Input('radius-slider', 'value'), Input('heat-slider', 'value'), Input('filter-switch', 'value')]
)
def update_map(radius, heat_val, filter_out):
    p_file = 'patients.xlsx'
    if not os.path.exists(p_file):
        return "<h1>File Not Found</h1>", html.P("patients.xlsx missing")

    try:
        df = pd.read_excel(p_file)
        
        # --- აი აქ არის მთავარი ცვლილება ---
        # ვქმნით ფიგურას, რომელიც მკაცრად 100% სიმაღლისაა
        fig = folium.Figure(width="100%", height="100%")
        m = folium.Map(
            location=[38.2527, -85.7585], 
            zoom_start=10, 
            tiles='CartoDB dark_matter'
        ).add_to(fig)
        # -----------------------------------

        # Clinics
        for _, h in hosp.iterrows():
            folium.Marker([h['Latitude'], h['Longitude']], 
                          icon=folium.Icon(color='red', icon='hospital', prefix='fa')).add_to(m)
            folium.Circle([h['Latitude'], h['Longitude']], radius=radius * 1609.34, 
                          color='red', fill=True, opacity=0.1).add_to(m)

        # Patients Logic
        df['Min_Dist'] = df.apply(lambda r: min([haversine(r['Latitude'], r['Longitude'], hl, hlo) 
                                               for hl, hlo in zip(hosp['Latitude'], hosp['Longitude'])]), axis=1)
        
        plot_df = df[df['Min_Dist'] > radius] if filter_out else df
        
        for _, r in plot_df.iterrows():
            folium.CircleMarker([r['Latitude'], r['Longitude']], radius=2.5, 
                               color="#00ffff" if r['Min_Dist'] > radius else "#888888", 
                               fill=True, fill_opacity=0.8).add_to(m)
        if not plot_df.empty:
            HeatMap([[r['Latitude'], r['Longitude'], heat_val] for _, r in plot_df.iterrows()], 
                    radius=15).add_to(m)

        # რუკის HTML-ის ექსპორტი ფიგურიდან
        map_html = fig.render()
        
        # დამატებითი დაზღვევა სქროლის წინააღმდეგ
        fixed_map_html = map_html.replace(
            '</head>', 
            '<style>html, body { margin: 0; padding: 0; height: 100%; overflow: hidden !important; }</style></head>'
        )

        covered = (len(df[df['Min_Dist'] <= radius]) / len(df)) * 100
        stats = html.Div([
            html.H2(f"{covered:.1f}%", className="text-danger fw-bold text-center mb-0"),
            html.P("TOTAL COVERAGE", className="text-muted small text-center")
        ])

        return fixed_map_html, stats

    except Exception as e:
        return f"<h1>Error: {str(e)}</h1>", html.P("Check console")

@app.callback(
    Output("download-excel", "data"),
    Input("btn-excel", "n_clicks"),
    State('radius-slider', 'value'),
    prevent_initial_call=True
)
def download_report(n, radius):
    df = pd.read_excel('patients.xlsx')
    df['Distance'] = df.apply(lambda row: min([haversine(row['Latitude'], row['Longitude'], hl, hlo) 
                                             for hl, hlo in zip(hosp['Latitude'], hosp['Longitude'])]), axis=1)
    df['Status'] = np.where(df['Distance'] <= radius, 'Covered', 'Gap')
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return dcc.send_bytes_content(output.getvalue(), "Health_Intel_Report.xlsx")

if __name__ == '__main__':
    app.run(debug=False, port=8050)