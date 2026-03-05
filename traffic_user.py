from astroquery.jplhorizons import Horizons
from IPython.display import IFrame
import pandas as pd, base64, json

def plot_ephemeris_aladin(
    object_id: str,
    location_code: str,
    *,
    # pass EITHER a time range (start/stop/step) ...
    start: str | None = None,
    stop: str | None = None,
    step: str | None = None,
    # ... OR a list of epochs (ISO strings or JD floats)
    epochs_list: list | None = None,
    fov_deg: float = 0.5,
    survey: str = "P/DSS2/color",
    width: int = 800,
    height: int = 600
):
    """
    Render an Aladin Lite viewer with:
      - magenta crosses at each Horizons ephemeris point
      - red 3σ uncertainty ellipses (RA_3sigma, DEC_3sigma)

    Parameters
    ----------
    object_id : Horizons target id (e.g. 'C/2025 N1', '4 Vesta', '2008 BJ22')
    location_code : Observatory/MPC code (e.g. 'X05' Rubin, '699' Lowell-LONEOS)
    start, stop, step : ISO strings & cadence for Horizons (UTC), e.g. '2025-08-05 02:30', '5m'
    epochs_list : alternative to start/stop/step — list of ISO strings or JD floats
    fov_deg : Aladin field-of-view in degrees
    survey : Aladin survey name
    width, height : IFrame size in pixels
    """
    # Build epochs argument for Horizons
    if epochs_list is not None:
        epochs_arg = epochs_list
    else:
        if not (start and stop and step):
            raise ValueError("Provide either epochs_list OR start+stop+step.")
        epochs_arg = {"start": start, "stop": stop, "step": step}

    # --- 1) Query Horizons ---
    h = Horizons(id=object_id, location=location_code, epochs=epochs_arg)
    df = h.ephemerides().to_pandas()

    # Normalize column names & ensure 3σ columns exist
    df = df.rename(columns={"RA":"RA_deg", "DEC":"DEC_deg"})
    if "RA_3sigma" in df.columns:
        df = df.rename(columns={"RA_3sigma":"RA3_asec"})
    else:
        df["RA3_asec"] = 0.0
    if "DEC_3sigma" in df.columns:
        df = df.rename(columns={"DEC_3sigma":"DEC3_asec"})
    else:
        df["DEC3_asec"] = 0.0

    # --- 2) Center & JS data payload ---
    ra0, dec0 = float(df.RA_deg.mean()), float(df.DEC_deg.mean())
    records = df[["RA_deg","DEC_deg","datetime_str","RA3_asec","DEC3_asec"]].to_dict("records")
    js_array = json.dumps(records)  # safe to embed in JS

    # --- 3) HTML+JS (Aladin Lite + markers + ellipses) ---
    template = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Aladin Lite</title>
  <script src="https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js"></script>
  <style>html,body {{margin:0; padding:0; height:100%;}}</style>
</head><body>
  <div id="aladin-lite-div" style="width:100%; height:100%;"></div>
  <script>
  A.init.then(() => {{
    const aladin = A.aladin('#aladin-lite-div', {{
      survey:   '{survey}',
      target:   '{ra0} {dec0}',
      fov:      {fov},
      cooFrame: 'ICRS'
    }});

    // Magenta crosses
    const trackLayer = A.catalog({{ name:'Track', shape:'cross', color:'magenta', sourceSize:10 }});
    aladin.addCatalog(trackLayer);

    // Red uncertainty ellipses via a graphic overlay
    const overlay = A.graphicOverlay({{ color:'red', lineWidth:2 }});
    aladin.addOverlay(overlay);

    const data = {js_array};

    data.forEach(d => {{
      // cross
      trackLayer.addSources([A.marker(d.RA_deg, d.DEC_deg, {{
        popupTitle: d.datetime_str,
        popupDesc:  'σ_RA=' + (d.RA3_asec/3600).toFixed(4) + '°, σ_Dec=' + (d.DEC3_asec/3600).toFixed(4) + '°'
      }})]);

      // ellipse at 3σ in RA/Dec (axis-aligned; rotation=0)
      const raSigDeg  = d.RA3_asec  / 3600.0;
      const decSigDeg = d.DEC3_asec / 3600.0;
      overlay.add(A.ellipse(d.RA_deg, d.DEC_deg, raSigDeg, decSigDeg, 0, {{}}));
    }});

    // simple rotate/flip controls (optional)
    const controls = document.createElement('div');
    controls.style = 'position:absolute;top:8px;right:8px;background:rgba(255,255,255,.85);padding:6px;font:12px sans-serif';
    controls.innerHTML = `
      <label>Rotate <input type="range" id="rot" min="0" max="360" value="0"></label><br>
      <label><input type="checkbox" id="flip"> Flip X</label>
    `;
    document.body.appendChild(controls);
    document.getElementById('rot').addEventListener('input', e => aladin.setRotation(parseInt(e.target.value)));
    document.getElementById('flip').addEventListener('change', e => {{
      document.getElementById('aladin-lite-div').style.transform = e.target.checked ? 'scaleX(-1)' : '';
    }});
  }});
  </script>
</body></html>
"""
    html = template.format(
        survey=survey,
        ra0=f"{ra0:.6f}",
        dec0=f"{dec0:.6f}",
        fov=f"{fov_deg:.3f}",
        js_array=js_array
    )

    # --- 4) Show via data-URI IFrame ---
    b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
    uri = "data:text/html;base64," + b64
    return IFrame(src=uri, width=width, height=height)