from plotly.offline import plot

import plotly.graph_objects as go
import plotly.express as px
import plotly.figure_factory as ff

import dash_bio as dashbio

from dash import dcc, html
from django_plotly_dash import DjangoDash
from dash.dependencies import Input, Output


def histogram_graphic(data, col_names, options):

    graph = px.bar(
        data, y=col_names[1], x=col_names[0], text_auto=True, width=options["width"]
    )
    # Customize aspect
    graph.update_traces(
        marker_color="rgb(158,202,225)",
        marker_line_color="rgb(8,48,107)",
        marker_line_width=1.5,
        opacity=0.6,
    )
    graph.update_layout(
        title=options["title"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_tickangle=-45,
        margin=dict(l=20, r=40, t=30, b=20),
    )

    plot_div = plot(graph, output_type="div", config={"displaylogo": False})

    return plot_div


def gauge_graphic(data):
    graph = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=data["value"],
            number={"suffix": "%"},
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Samples Analized in percentage"},
            gauge={"axis": {"range": [None, 100]}},
        )
    )
    graph.update_layout(margin=dict(t=20, b=10, l=20, r=30))
    plot_div = plot(graph, output_type="div", config={"displaylogo": False})

    return plot_div


def bullet_graphic(value, title):
    point = str(value)
    top_value = int(value)
    data = [
        {
            "label": "Upload %",
            "range": [40, 70, 100],
            "performance": [40, top_value],
            "point": [point],
        }
    ]

    measure_colors = ["rgb(68, 107, 162)", "rgb(0, 153, 0)"]
    fig = ff.create_bullet(
        data,
        titles="label",
        title="",
        markers="point",
        measures="performance",
        ranges="range",
        orientation="v",
        measure_colors=measure_colors,
        margin=dict(
            t=25,
            r=0,
            b=0,
            l=0,
        ),
    )
    fig.update_layout(height=450, width=330)
    plot_div = plot(fig, output_type="div")
    return plot_div


def pie_graphic(data, names, title, show_legend=False):
    colors = [
        "cyan",
        "red",
        "gold",
        "darkblue",
        "darkred",
        "magenta",
        "darkorange",
        "turquoise",
    ]
    fig = go.Figure(
        data=go.Pie(
            labels=names,
            values=data,
        )
    )
    fig.update_traces(
        title=title,
        title_font=dict(size=15, family="Verdana", color="darkgreen"),
        marker=dict(colors=colors, line=dict(color="black", width=1)),
    )
    fig.update_layout(
        height=350, width=270, showlegend=show_legend, margin=dict(t=0, b=0, l=0, r=0)
    )
    plot_div = plot(fig, output_type="div", config={"displaylogo": False})
    return plot_div


def needle_plot(m_data):
    """
    import json
    import urllib.request as urlreq

    data = urlreq.urlopen("https://git.io/needle_PIK3CA.json").read().decode("utf-8")

    mdata = json.loads(data)
    """
    """
    fig = dashbio.NeedlePlot(
        id='dashbio-default-needleplot',
        mutationData=mdata,
        height=450,
    )
    """
    app = DjangoDash("sampleVariantGraphic")
    # mdata["domains"] = m_data["domains"]
    # m_data["x"] = mdata["x"][48:72]
    # m_data["y"] = mdata["y"][48:72]
    # m_data["mutationGroups"] = mdata["mutationGroups"][48:72]
    # m_data["domains"] = mdata["domains"]
    # import pdb; pdb.set_trace()
    app.layout = html.Div(
        [
            "Show or hide range slider",
            dcc.Dropdown(
                id="default-needleplot-rangeslider",
                options=[{"label": "Show", "value": 1}, {"label": "Hide", "value": 0}],
                clearable=False,
                multi=False,
                value=1,
                style={"width": "400px"},
            ),
            dashbio.NeedlePlot(
                id="dashbio-default-needleplot",
                mutationData=m_data,
                height=550,
                width=700,
                domainStyle={
                    "displayMinorDomains": True,
                    # 'domainColor': ['#FFDD00', '#00FFDD', '#0F0F0F', '#D3D3D3']
                },
                # domainStyle={"textangle": -45},
            ),
        ]
    )

    @app.callback(
        Output("dashbio-default-needleplot", "rangeSlider"),
        Input("default-needleplot-rangeslider", "value"),
    )
    def update_needleplot(show_rangeslider):
        return True if show_rangeslider else False
