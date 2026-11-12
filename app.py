import csv,io,re,shutil,subprocess,tempfile
from pathlib import Path
from fastapi import FastAPI,UploadFile,File,HTTPException
from fastapi.responses import HTMLResponse,StreamingResponse
from fastapi.staticfiles import StaticFiles
app=FastAPI(title='PCB Studio',version='0.1.0')
app.mount('/static',StaticFiles(directory='static'),name='static')
def parse_board(t):
 layers=[]; nets=re.findall(r'\(net\s+\d+\s+"([^"]*)"\)',t); parts=[]
 lb=re.search(r'\(layers\s+(.*?)\n\s*\)',t,re.S)
 if lb: layers=[{'id':a,'name':b} for a,b in re.findall(r'\(\s*(\d+)\s+"([^"]+)"',lb.group(1))]
 for block in re.findall(r'\(footprint\b.*?(?=\n\s*\(footprint\b|\Z)',t,re.S):
  ref=re.search(r'\(property\s+"Reference"\s+"([^"]+)"',block); val=re.search(r'\(property\s+"Value"\s+"([^"]+)"',block)
  if ref: parts.append({'reference':ref.group(1),'value':val.group(1) if val else '','source':'PCB'})
 return {'kind':'KiCad PCB','layers':layers,'nets':sorted(set(nets)),'components':parts}
def parse_schematic(t):
 parts=[]
 for block in re.findall(r'\(symbol\b.*?(?=\n\s*\(symbol\b|\Z)',t,re.S):
  ref=re.search(r'\(property\s+"Reference"\s+"([^"]+)"',block); val=re.search(r'\(property\s+"Value"\s+"([^"]+)"',block)
  if ref and not ref.group(1).startswith('#'): parts.append({'reference':ref.group(1),'value':val.group(1) if val else '','source':'Schematic'})
 return {'kind':'KiCad Schematic','layers':[],'nets':[],'components':list({p['reference']:p for p in parts}.values())}
async def read_file(f):
 n=(f.filename or '').lower()
 if not(n.endswith('.kicad_pcb') or n.endswith('.kicad_sch')): raise HTTPException(400,'Upload a .kicad_pcb or .kicad_sch file.')
 raw=await f.read()
 if len(raw)>10*1024*1024: raise HTTPException(413,'File exceeds 10 MB.')
 try: t=raw.decode('utf-8')
 except UnicodeDecodeError: raise HTTPException(400,'File is not UTF-8 text.')
 return n,t
@app.get('/',response_class=HTMLResponse)
async def home(): return Path('static/index.html').read_text(encoding='utf-8')
@app.get('/api/health')
async def health(): return {'status':'ok','kicad_cli':bool(shutil.which('kicad-cli'))}
@app.post('/api/inspect')
async def inspect(file:UploadFile=File(...)):
 n,t=await read_file(file); d=parse_board(t) if n.endswith('.kicad_pcb') else parse_schematic(t); d.update(filename=file.filename,component_count=len(d['components']),net_count=len(d['nets']),layer_count=len(d['layers'])); return d
@app.post('/api/export-bom')
async def bom(file:UploadFile=File(...)):
 n,t=await read_file(file); d=parse_board(t) if n.endswith('.kicad_pcb') else parse_schematic(t); o=io.StringIO(); w=csv.DictWriter(o,fieldnames=['reference','value','source']); w.writeheader(); w.writerows(d['components']); return StreamingResponse(iter([o.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="pcb-studio-bom.csv"'})
async def run_check(f,kind):
 cli=shutil.which('kicad-cli')
 if not cli: raise HTTPException(503,'kicad-cli not found. Install KiCad and add its bin folder to PATH.')
 n,t=await read_file(f); suffix='.kicad_pcb' if kind=='drc' else '.kicad_sch'
 if not n.endswith(suffix): raise HTTPException(400,f'{kind.upper()} requires {suffix}.')
 with tempfile.TemporaryDirectory() as td:
  src=Path(td)/('input'+suffix); out=Path(td)/'report.txt'; src.write_text(t,encoding='utf-8')
  try: p=subprocess.run([cli,kind,'--output',str(out),str(src)],capture_output=True,text=True,timeout=90)
  except subprocess.TimeoutExpired: raise HTTPException(504,'KiCad check timed out.')
  report=out.read_text(errors='replace') if out.exists() else p.stdout+'\n'+p.stderr
  return {'check':kind.upper(),'return_code':p.returncode,'report':report[:20000],'note':'Review results in KiCad before manufacturing.'}
@app.post('/api/drc')
async def drc(file:UploadFile=File(...)): return await run_check(file,'drc')
@app.post('/api/erc')
async def erc(file:UploadFile=File(...)): return await run_check(file,'erc')
