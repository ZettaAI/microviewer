import os
from typing import Optional
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import webbrowser

import numpy as np

DEFAULT_PORT = 8080

def to3d(img):
  # RGB color image
  if len(img.shape) == 4 and img.dtype == np.uint8 and img.shape[3] == 3:
    colorized = np.full(img.shape[:3], fill_value=(0xff << 24), order="F", dtype=np.uint32)
    colorized[:,:,:] |= img[:,:,:,0].astype(np.uint32)
    colorized[:,:,:] |= img[:,:,:,1].astype(np.uint32) << 8
    colorized[:,:,:] |= img[:,:,:,2].astype(np.uint32) << 16
    return colorized

  while len(img.shape) > 3:
    img = img[..., 0]
  while len(img.shape) < 3:
    img = img[..., np.newaxis]
  return img  

def hyperview(
  img:np.ndarray, 
  seg:np.ndarray, 
  resolution:Optional[np.ndarray] = np.ones((3,), dtype=int), 
  offset:Optional[np.ndarray] = np.zeros((3,), dtype=int),
  cloudpath:str = "IN MEMORY", 
  hostname:str = "localhost",
  port=DEFAULT_PORT,
  browser=True,
):

  img = to3d(img)
  seg = to3d(seg)

  assert np.all(img.shape[:3] == seg.shape[:3])

  img_data = {
    "img": img,
    "cloudpath": cloudpath,
    "resolution": resolution,
    "layer_type": 'image',
    "offset": offset,
  }

  seg_data = {
    "img": seg,
    "cloudpath": cloudpath,
    "resolution": resolution,
    "layer_type": 'segmentation',
    "offset": offset,
  }

  return run([ img_data, seg_data ], hostname=hostname, port=port, browser=browser)

def view(
  img:np.ndarray, 
  seg:bool = False, 
  resolution:Optional[np.ndarray] = np.ones((3,), dtype=int), 
  offset:Optional[np.ndarray] = np.zeros((3,), dtype=int),
  cloudpath:str = "IN MEMORY", 
  hostname:str = "localhost",
  port=DEFAULT_PORT,
  browser=True,
):
  img = to3d(img)

  data = {
    "img": img,
    "cloudpath": cloudpath,
    "resolution": resolution,
    "layer_type": ('segmentation' if seg else 'image'),
    "offset": offset,
  }

  return run([ data ], hostname=hostname, port=port, browser=browser)

def run(cutouts, hostname="localhost", port=DEFAULT_PORT, browser=True):
  """Start a local web app on the given port that lets you explore this cutout."""
  def handler(*args):
    return ViewerServerHandler(cutouts, *args)

  myServer = HTTPServer((hostname, port), handler)
  url = f"http://{hostname}:{port}"
  print(f"Viewer server listening to {url}")

  if browser:
    webbrowser.open(url, new=2)

  try:
    myServer.serve_forever()
  except KeyboardInterrupt:
    print("")
  finally:
    myServer.server_close()

class ViewerServerHandler(BaseHTTPRequestHandler):
  def __init__(self, cutouts, *args):
    self.cutouts = cutouts
    BaseHTTPRequestHandler.__init__(self, *args)

  def do_GET(self):
    self.send_response(200)
  
    allowed_files = ('/', '/datacube.js', '/jquery-3.7.0.min.js', '/favicon.ico')

    if self.path in allowed_files:
      self.serve_file()
    elif self.path == '/parameters':
      self.serve_parameters()
    elif self.path == '/channel':
      self.serve_data(self.cutouts[0]['img'])
    elif self.path == '/segmentation':
      self.serve_data(self.cutouts[1]['img'])

  def serve_data(self, data):
    self.send_header('Content-type', 'application/octet-stream')
    self.send_header('Content-length', str(data.nbytes))
    self.end_headers()
    self.wfile.write(data.tobytes('F'))

  def serve_parameters(self):
    self.send_header('Content-type', 'application/json')
    self.end_headers()

    cutout = self.cutouts[0]
    offset = cutout['offset']
    shape = cutout['img'].shape
    bounds =[ 
      int(offset[0]), 
      int(offset[1]), 
      int(offset[2]),
      (int(offset[0]) + shape[0]), 
      (int(offset[1]) + shape[1]), 
      (int(offset[2]) + shape[2])
    ]

    if len(self.cutouts) == 1:
      img = cutout["img"]
      msg = json.dumps({
        'viewtype': 'single',
        'layer_type': cutout['layer_type'],
        'cloudpath': [ cutout['cloudpath'] ],
        'bounds': bounds,
        'resolution': [ int(x) for x in cutout['resolution'] ],
        'data_types': [ str(img.dtype) ],
        'data_bytes': int(np.dtype(img.dtype).itemsize),
      })
    else:
      img, seg = self.cutouts
      msg = json.dumps({
        'viewtype': 'hyper',
        'cloudpath': [ img['cloudpath'], seg['cloudpath'] ],
        'bounds': bounds,
        'resolution': [ int(x) for x in cutout['resolution'] ],
        'data_types': [ str(img["img"].dtype), str(seg["img"].dtype) ],
        'data_bytes': [ 
          np.dtype(img["img"].dtype).itemsize,
          np.dtype(seg["img"].dtype).itemsize
        ],
      })
    self.wfile.write(msg.encode('utf-8'))

  def serve_file(self):
    self.send_header('Content-type', 'text/html')
    self.end_headers()

    path = self.path.replace('/', '')

    if path == '':
      path = 'index.html'

    dirname = os.path.dirname(__file__)
    filepath = os.path.join(dirname, './' + path)
    with open(filepath, 'rb') as f:
      self.wfile.write(f.read())  

  # silent, no need to print that it's serving html and js
  def log_message(self, format, *args):
    pass

