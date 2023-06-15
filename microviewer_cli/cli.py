import gzip
import io
import lzma
import os
import sys

import click
import microviewer
import numpy as np

class Tuple234(click.ParamType):
  """A command line option type consisting of 3 comma-separated integers."""
  name = 'tuple234'
  def convert(self, value, param, ctx):
    if isinstance(value, str):
      try:
        value = tuple(map(int, value.split(',')))
      except ValueError:
        self.fail(f"'{value}' does not contain a comma delimited list of 3 or 4 integers.")
      if len(value) not in (2,3,4):
        self.fail(f"'{value}' does not contain a comma delimited list of 3 or 4 integers.")
    return value

def root_file_ext(filename):
  filename, ext = os.path.splitext(filename)

  while True:
    filename, ext2 = os.path.splitext(filename)
    if ext2 == '':
      return ext
    ext = ext2

def load_bytesio(filelike):
  if hasattr(filelike, 'read'):
    binary = filelike.read()
  elif (
    isinstance(filelike, str) 
    and os.path.splitext(filelike)[1] == '.gz'
  ):
    with gzip.open(filelike, 'rb') as f:
      binary = f.read()
  elif (
    isinstance(filelike, str) 
    and os.path.splitext(filelike)[1] in ('.lzma', '.xz')
  ):
    with lzma.open(filelike, 'rb') as f:
      binary = f.read()
  else:
    with open(filelike, 'rb') as f:
      binary = f.read()
  
  return io.BytesIO(binary)

# c/o https://stackoverflow.com/questions/64226337/is-there-a-way-to-read-npy-header-without-loading-the-whole-file
def read_numpy_array_header(fobj):
  version = np.lib.format.read_magic(fobj)
  func_name = 'read_array_header_' + '_'.join(str(v) for v in version)
  func = getattr(np.lib.format, func_name)
  return func(fobj)

def load_numpy(src, shape, dtype, order):
  try:
    with open(src, "rb") as f:
      shape, forder, dtype = read_numpy_array_header(f)
      order = "F" if forder else "C"
  except ValueError:
    if dtype is None or shape is None or order not in ("C", "F"):
      raise
    dtype = np.dtype(dtype)

  return np.memmap(src, dtype=dtype, shape=shape, order=order, mode="r")

def load(filename, shape, dtype, order):
  binary = load_bytesio(filename)
  ext = root_file_ext(filename)

  if ext == ".npy":
    image = load_numpy(filename, shape, dtype, order)
  elif ext == ".nii":
    import nibabel as nib
    image = nib.load(filename)
    image = np.array(image.dataobj)
  else:
    raise ValueError("Data type not supported.")

  return image

@click.command()
@click.argument("image")
@click.argument("segmentation", required=False, default=None)
@click.option('--seg', is_flag=True, default=False, help="Display image as segmentation.", show_default=True)
@click.option('--browser/--no-browser', default=True, is_flag=True, help="Open the dataset in the system's default web browser.", show_default=True)
@click.option('--shape', type=Tuple234(), default=None, help="Set shape manually for memmaps.", show_default=True)
@click.option('--dtype', type=str, default=None, help="Set dtype manually for memmaps.", show_default=True)
@click.option('--order', type=str, default="F", help="Set order manually for memmaps.", show_default=True)
def main(image, segmentation, seg, browser, shape, dtype, order):
  """
  View 3D images in the browser.
  """
  try:
    image_np = load(image, shape, dtype, order)
    if segmentation:
      segmentation_np = load(segmentation, shape, dtype, order)
  except ValueError:
    print("Data type not supported.")
    return

  if segmentation is not None:
    microviewer.hyperview(
      image_np, segmentation_np, 
      browser=browser, 
      cloudpath=[ image, segmentation ],
    )
  else:
    microviewer.view(
      image_np, seg=seg, 
      browser=browser, cloudpath=image
    )
