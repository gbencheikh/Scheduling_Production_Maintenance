# gantt_chart.py
import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output, State
from collections import OrderedDict

def create_gantt_chart(ressources, bars, title="GANTT", cell_widht=50, cell_height=30, rows_spacement=20):
    app = dash.Dash(__name__)

    ## CALCUL DES NOMBRES DE LIGNE ET COLONNE
    x = int(max(bars, key=lambda x: x['end'])['end'])
    # cell_widht = 100/x
    unique_tasks = []
    for bar in bars:
        task = bar['task']
        if task not in unique_tasks:
            unique_tasks.append(task)
    y = len(unique_tasks)
    grouped_by_start_task = {}

    ## REGROUPEMENT DES TACHES AYANT LE MEME DEBUT
    for bar in bars:
        key = (bar['start'], bar['task'])
        if key not in grouped_by_start_task:
            grouped_by_start_task[key] = []
        grouped_by_start_task[key].append(bar)
    for (start_value, task_value), grouped_elements in grouped_by_start_task.items():
        concatenated_info = '\n'.join(element['info'] for element in grouped_elements)
        for element in grouped_elements:
            element['info'] = concatenated_info

    ## AFFICHAGE DE L'AXE DES ABSCISSES
    x_axis = []
    html_x_axis = html.Div(style={'display':'flex', 'margin-left': f'{cell_widht/2}px'})
    for i in range(x+1):
        time = html.Div(
            children=f'{i*1}',
            style={
                'width':f'{cell_widht-1}px',
                'margin-right' : '1px',
                'text-align': 'center',
            }
        )
        x_axis.append(time)

    ## AFFICHAGE DE L'AXE DES ORDONNEES
    y_axis = []
    for i in range(y):
        html_y_axis = html.Div(
            children=html.Div(children = f'{unique_tasks[i]}')
        )
        style = {
            'display':'flex',
            'height': f'{cell_height}px',
            'margin-right': '5px',
            'margin-bottom': f'{rows_spacement}px',
            'text-align': 'right',
            'align-items': 'center',
        }
        html_y_axis.style = style
        y_axis.append(html_y_axis)

    ## AFFICHAGE DE LA GRILLE
    grid = []
    html_grid = html.Div()
    for j in range(y+1):
        row = []
        html_row = html.Div()
        html_row.style = {
            'display' : 'flex',
            'margin-bottom':'1px'
        }
        for i in range(x+2):
            html_columns = html.Div()
            html_columns.style = {
                'background-color':'#e5ecf6',
                'width':f'{cell_widht-1}px',
                'height':f'{cell_height+rows_spacement-1}px',
                'margin-right' : '1px',
            }
            row.append(html_columns)
        html_row.children = row
        grid.append(html_row)

    ## AFFICHAGE DES BARS
    gantt = []
    for bar in bars:
        duration = bar['end']-bar['start']
        start = bar['start']
        task = unique_tasks.index(bar['task']) 
        color = ressources[bar['rsc']]
        label = bar['label']
        info = bar['info']
        html_bar =  html.Div(
            title=f'{info}',
            children=html.Div(children = f'{label}'),
            className=f'{bar["rsc"]}',
        )
        style = {
            'display':'flex',
            'align-items':'center',
            'justify-content':'center',
            'position':'absolute',
            'background-color' : f'{color}',
            'width': f'{cell_widht*duration-1}px',
            'height': f'{cell_height}px',
            'margin-right': '1px',
            'margin-left': f'{start*cell_widht+cell_widht}px',
            'margin-top': f'{(cell_height+rows_spacement)*task+(cell_height/2+rows_spacement)}px',
            'color':'white',
        }
        html_bar.style = style
        gantt.append(html_bar)
    html_x_axis.children = x_axis
    html_grid.children= grid
    gantt.append(html_grid)
    gantt.append(html_x_axis) 

    ## AFFICHAGE DE LA LEGENDE
    legend_items = {}
    for bar in bars:
        name = bar['rsc']
        color = ressources[bar['rsc']]
        if name not in legend_items:
            legend_items[name] = color
    legend_items = OrderedDict(sorted(legend_items.items()))
    legend_html = []
    for name, color in legend_items.items():
        legend_item = html.Div(
            style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '5px'},
            children=[
                html.Div(
                    style={
                        'background-color': color,
                        'width': '30px',
                        'height': '10px',
                        'margin-right': '10px',
                        'cursor': 'pointer'
                    },
                    id=f'legend-{name}',
                ),
                html.Span(name)
            ]
        )
        legend_html.append(legend_item)


    app.layout = html.Div(children=[
        html.H3(children=f"{title}", id='title'),
        html.Div(id="container", style={'font': 'x-small', 'overflow':'auto', 'display':'flex', 'border':'1px solid #eb687b21', 'padding':f'{cell_height}px', 'width':'auto'}, children=[
            html.Div(id="y_axis", style={'margin-top': f'{cell_height/2+rows_spacement}px'}, children=y_axis),
            html.Div(id="figure", style={'position':'relative'}, children=gantt),
            html.Div(id="legende", style={'margin-left': '10px'}, children=legend_html),
        ]),
    ])
    @app.callback(
        Output('figure', 'children'),
        [Input(f'legend-{name}', 'n_clicks') for name in legend_items.keys()],
        [State('figure', 'children')]
    )
    def update_gantt(*args):
        clicks = args[:-1]
        children = args[-1]
        bars = children[:-2]
        resp=title
        # print(children)
        for i, name in enumerate(legend_items):
            if clicks[i] and clicks[i] % 2 :
                for bar in bars:
                    if isinstance(bar, dict) and f'{name}' in bar['props']['className']:
                        bar['props']['style']['display'] = 'none'
            elif clicks[i] and not(clicks[i] % 2):
                for bar in bars :
                    if isinstance(bar, dict) and f'{name}' in bar['props']['className']:
                        bar['props']['style']['display'] = 'flex'
                    

        return children
    return app