import sys
from os import path
from astropy.io import fits
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from getkey import getkey

### START PARAMETERS BLOCK ####################################################

# What vertical slice of the image to extract:
x0, x1 = 1500, 1550

# What part of the image around the spectrum to ignore when calculating the mean background value.
# If bin_size is 20, we'll ignore +20px/-20px around the spectrum, so a total window of 40px
bin_size = 20

# Image scale in arcsecond per pixel
image_scale = 0.89

### END PARAMETERS BLOCK ######################################################

dir = sys.argv[1] if len(sys.argv) > 1 else '.'

if not path.isdir(dir):
  sys.exit(f"{dir} does not seem to be a valid directory.")

def measure_fwhm(event):
  # Load the image data - TODO: add try/except
  image = fits.open(event.src_path)
  imageData = image[0].data

  # Extract a vertical slice of the image:
  sliceData = imageData[:, x0:x1]

  # plt.figure(figsize=(12,12))

  # plt.subplot(3, 1, 1)
  # plt.imshow(sliceData, cmap='gray')

  # Extract a profile from that vertical slice:
  values = np.mean(sliceData, axis=1)

  # Get position of the spectrum (where the value is maximum)
  maxIndex = np.argmax(values)

  # Get background value
  background = np.concatenate((values[:maxIndex-bin_size], values[maxIndex+bin_size:]))
  backgroundValue = np.mean(background, axis=0)
  # print(f"Background value is {backgroundValue}")

  # Subtract the background
  values = np.subtract(values, backgroundValue)

  # Get the maximum value:
  maxValue = values[maxIndex]

  # Define model function to be used to fit to the data above:
  def gauss(x, *p):
    A, mu, sigma = p
    return A*np.exp(-(x-mu)**2/(2.*sigma**2))

  xdata = np.arange(0, len(values))

  # plt.subplot(3, 1, 2)
  # plt.scatter(xdata, values)

  # p0 is the initial guess for the fitting coefficients (A, mu and sigma above)
  p0 = [maxValue, maxIndex, 3]

  coeff, var_matrix = curve_fit(gauss, xdata, values, p0=p0)
  A, mu, sigma = coeff

  # fitted_gaussian_curve = gauss(xdata, *coeff)
  # plt.subplot(3, 1, 3)
  # plt.plot(xdata, fitted_gaussian_curve, label='Fitted curve')

  # plt.show()

  print(f"FWHM = {sigma * 2:.2f}px -> {sigma * 2 * image_scale:.2f}\"")

event_handler = PatternMatchingEventHandler(patterns=["*.fit", "*.fits"], ignore_directories=True)
event_handler.on_created = measure_fwhm

observer = Observer()
observer.schedule(event_handler, dir, recursive=False)
observer.start()

print(f"Watching directory {dir}.\nPress 'q' to exit.")

key = getkey()
if key == 'q':
  observer.stop()
  observer.join()
