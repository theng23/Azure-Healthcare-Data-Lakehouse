#!/usr/bin/env python3
"""Render compact logical diagrams of the supplied ADF graphs.

Requires Pillow. PNG and SVG outputs are documentation, not Azure screenshots.
Review the matching ADF JSON if changing an activity or dependency.
"""
from pathlib import Path
import html
import math
import textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'docs/images'
PALETTE = {'control': ('#EAF3FB', '#236DA8'), 'copy': ('#E6F5F4', '#087F80'),
           'notebook': ('#F1ECFB', '#7650AC'), 'condition': ('#FFF4DE', '#AA731B'),
           'success': ('#EAF5EB', '#367C45'), 'failure': ('#FCEDEC', '#B34E48'),
           'secret': ('#F0EFF8', '#63577F')}


def font(size, bold=False):
    names = ['DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf',
             'arialbd.ttf' if bold else 'arial.ttf']
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    raise RuntimeError('Install DejaVu Sans or Arial to render documentation images')


class Diagram:
    def __init__(self, name, title, subtitle, height, width=1600):
        self.name, self.width, self.height = name, width, height
        self.image = Image.new('RGB', (width, height), 'white')
        self.d = ImageDraw.Draw(self.image)
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>']
        self.nodes = {}
        self.text(64, 44, title, 40, True)
        self.text(64, 108, subtitle, 24, color='#516172')

    def text(self, x, y, label, size=25, bold=False, color='#162D40', center=False):
        ft = font(size, bold)
        anchor = 'mm' if center else 'lt'
        self.d.text((x, y), label, font=ft, fill=color, anchor=anchor)
        # SVG uses middle baseline for centered text; top-aligned text is offset.
        self.parts.append(f'<text x="{x}" y="{y if center else y+size}" text-anchor="{"middle" if center else "start"}" dominant-baseline="{"middle" if center else "auto"}" font-family="DejaVu Sans,Arial,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{html.escape(label)}</text>')

    def node(self, key, x, y, w, h, label, kind='control', size=25):
        fill, stroke = PALETTE[kind]
        self.d.rounded_rectangle((x,y,x+w,y+h), radius=15, fill=fill, outline=stroke, width=3)
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="15" fill="{fill}" stroke="{stroke}" stroke-width="3"/>')
        lines = label.split('\n')
        lineh = size + 10
        for i, line in enumerate(lines):
            self.text(x+w/2, y+h/2 + (i-(len(lines)-1)/2)*lineh, line, size, center=True)
        self.nodes[key] = (x,y,w,h)

    def line(self, points, color='#718499', arrow=True):
        self.d.line(points, fill=color, width=4, joint='curve')
        self.parts.append('<polyline points="' + ' '.join(f'{x},{y}' for x,y in points) + f'" fill="none" stroke="{color}" stroke-width="4"/>')
        if arrow:
            x,y = points[-1]; px,py=points[-2]; angle=math.atan2(y-py,x-px)
            polygon=[(x,y),(x-16*math.cos(angle-.45),y-16*math.sin(angle-.45)),(x-16*math.cos(angle+.45),y-16*math.sin(angle+.45))]
            self.d.polygon(polygon, fill=color)
            self.parts.append('<polygon points="'+' '.join(f'{a},{b}' for a,b in polygon)+f'" fill="{color}"/>')

    def edge(self, a, b, label=None, color='#718499'):
        x,y,w,h=self.nodes[a]; xx,yy,ww,hh=self.nodes[b]
        if yy >= y+h:
            start=(x+w/2,y+h);end=(xx+ww/2,yy)
            mid=(start[1]+end[1])/2
            points=[start,(start[0],mid),(end[0],mid),end]
        elif xx >= x+w:
            start=(x+w,y+h/2);end=(xx,yy+hh/2)
            mid=(start[0]+end[0])/2
            points=[start,(mid,start[1]),(mid,end[1]),end]
        else:
            start=(x,y+h/2);end=(xx+ww,yy+hh/2)
            mid=(start[0]+end[0])/2
            points=[start,(mid,start[1]),(mid,end[1]),end]
        self.line(points,color)
        if label:
            self.text((start[0]+end[0])/2+10,(start[1]+end[1])/2-23,label,20,color=color)

    def note(self, y, lines):
        for i,line in enumerate(lines):
            self.text(64,y+i*33,line,23,color='#516172')

    def save(self):
        self.text(64,self.height-48,'Logical diagram from repository JSON  |  Not an Azure UI screenshot',20,color='#6A7785')
        DEST.mkdir(parents=True,exist_ok=True)
        self.image.save(DEST/f'{self.name}.png')
        (DEST/f'{self.name}.svg').write_text('\n'.join(self.parts+['</svg>']),encoding='utf-8')


def render():
    d=Diagram('01-pl-master','PL_MASTER','Two parallel source branches, followed by Gold and notification',900)
    d.node('pg',170,220,510,110,'Source to Silver Postgres\nneon_postgres')
    d.node('csv',920,220,510,110,'Source to Silver ADLS CSV\nadls_csv')
    d.node('gold',545,450,510,105,'Silver to Gold\nPL_SILVER_TO_GOLD','notebook')
    d.node('email',545,665,510,95,'Send_Email\nPL_SEND_EMAIL')
    d.edge('pg','gold','Succeeded');d.edge('csv','gold','Succeeded');d.edge('gold','email','Succeeded')
    d.note(155,['Scheduled entry: TGR_CARESYNC_DAILY, every 8 hours, UTC+7'])
    d.save()

    d=Diagram('02-pl-source-to-silver-main','PL_SOURCE_TO_SILVER_MAIN','Parameters: source_system, adf_run_id  |  Parallel ForEach over active tables',1000)
    d.node('lookup',480,190,640,100,'Read Source Tables List\nActive SOURCE_TO_SILVER metadata')
    d.node('audit',520,380,560,95,'Insert In Progress Status')
    d.node('inner',520,560,560,100,'Ingest from Source to Silver\nPL_SOURCE_TO_SILVER_INNER')
    d.node('logfail',190,770,520,95,'Update Failed Status','failure')
    d.node('fail',890,770,520,95,'Update pipeline as failed','failure')
    d.edge('lookup','audit');d.edge('audit','inner');d.edge('inner','logfail','Failed','#B34E48');d.edge('inner','fail','Failed','#B34E48')
    d.note(915,['Success status is written by the inner pipeline; the parent waits for each call.'])
    d.save()

    d=Diagram('03-pl-source-to-silver-inner','PL_SOURCE_TO_SILVER_INNER','Parameters: table_id, adf_run_id  |  One table and one Landing batch',1500)
    d.node('details',190,190,510,95,'Read Table Details')
    d.node('time',900,190,510,95,'Set Start Time\nBatch-folder timestamp')
    d.node('load',470,390,660,110,'Check Load Type\nNon-FULL: read and store watermark','condition')
    d.node('switch',500,600,600,90,'Check Source System','condition')
    d.node('pg',125,800,590,110,'Source to Landing Ingestion\nPostgreSQL to Parquet','copy')
    d.node('csv',885,800,590,110,'Ingest CSV from source to Landing\nBinary file copy','copy',24)
    d.node('bronze',520,1010,560,90,'Landing to Bronze','notebook')
    d.node('silver',520,1170,560,90,'Bronze to Silver','notebook')
    d.node('success',170,1350,540,85,'Update Success Status','success')
    d.node('wm',890,1350,540,85,'Update watermark if non-FULL','condition',24)
    d.edge('details','load');d.edge('time','load');d.edge('load','switch');d.edge('switch','pg','neon_postgres');d.edge('switch','csv','adls_csv')
    d.edge('pg','bronze');d.edge('csv','bronze');d.edge('bronze','silver');d.edge('silver','success');d.edge('silver','wm')
    d.save()

    d=Diagram('04-pl-silver-to-gold','PL_SILVER_TO_GOLD','Parameter: adf_run_id  |  Parallel ForEach over active Gold metadata',1120)
    d.node('lookup',450,190,700,100,'Read Source Tables List\nActive SILVER_TO_GOLD metadata')
    d.node('audit',520,380,560,90,'Insert In Progress Status')
    d.node('gold',470,560,660,105,'Silver to Gold\nGold/NB_<gold_table_name>','notebook')
    d.node('ok',80,800,440,100,'Update Success Status\nReturned row count','success')
    d.node('log',590,800,440,100,'Update Failed Status','failure')
    d.node('fail',1100,800,420,100,'The Gold notebook failed','failure',23)
    d.edge('lookup','audit');d.edge('audit','gold');d.edge('gold','ok','Succeeded','#367C45');d.edge('gold','log','Failed','#B34E48');d.edge('gold','fail','Failed','#B34E48')
    d.note(965,['Supplied models: patient_360, hospital_daily_summary, lab_test_trends', 'All three notebooks fully rebuild their Gold output tables.'])
    d.save()

    d=Diagram('05-pl-send-email','PL_SEND_EMAIL','Parameter: adf_run_id  |  Audit summary and runtime Key Vault secret lookup',1280)
    d.node('status',70,210,380,100,'Read All Tables Status\nAudit rows for this run',size=23)
    d.node('count',490,210,380,100,'Check overall failed count',size=23)
    d.node('header',910,210,290,100,'Prepare Email\nBody Header',size=23)
    d.node('footer',1240,210,290,100,'Prepare Email\nBody Footer',size=23)
    d.node('subject',490,420,380,95,'Prepare Email Subject',size=23)
    d.node('body',500,650,600,95,'Prepare logic app body')
    d.node('vault',500,850,600,105,'Get Logic App URL\nKey Vault GET using ADF identity','secret',24)
    d.node('post',500,1060,600,95,'Send Email\nHTTP POST to Logic Apps','copy')
    d.edge('count','subject')
    for key in ['status','subject','header','footer']:
        x,y,w,h = d.nodes[key]
        d.line([(x+w/2,y+h),(x+w/2,590),(800,590),(800,650)])
    d.edge('body','vault');d.edge('vault','post')
    d.note(1190,['The master invokes this pipeline only after Gold succeeds.'])
    d.save()

    d=Diagram('architecture','CareSync end to end architecture','One GitHub repository for ADF orchestration and Databricks transformations',1160)
    d.node('pg',170,190,510,95,'Neon PostgreSQL\nRelational source','copy')
    d.node('csv',920,190,510,95,'ADLS source container\nCSV files','copy')
    d.node('landing',500,420,600,105,'ADF Copy to Landing\nTimestamped Parquet or file batches','copy',24)
    d.node('bronze',110,665,420,105,'Bronze\nAppend raw batch','notebook')
    d.node('silver',590,665,420,105,'Silver\nFULL / APPEND / MERGE','notebook',24)
    d.node('gold',1070,665,420,105,'Gold\nThree analytical tables','notebook',24)
    d.edge('pg','landing');d.edge('csv','landing');d.edge('landing','bronze');d.edge('bronze','silver');d.edge('silver','gold')
    d.note(855,['ADF orchestrates all stages; Azure SQL stores metadata, watermarks and audit rows.',
                'Key Vault stores secrets; Logic Apps handles the notification request and email.',
                'GitHub Actions validates the repository and imports Databricks notebooks.',
                'ADF authoring uses /adf and publishes separately to the live factory.'])
    d.save()


if __name__ == '__main__':
    render()
    print('Rendered architecture and five pipeline diagrams as PNG and SVG.')
