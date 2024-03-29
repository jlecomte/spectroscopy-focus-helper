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

# What vertical slice of the image to extract, expressed in pixels.
#
#                x0                     x1
#                |                      |
#   ----------------------------------------------------
#   /////////////|                      |///////////////
#   /////////////|                      |///////////////
#   /////////////|                      |///////////////
#
# Pick values that are near the center of your sensor, where aberrations are
# going to be minimal. Also pick a range that is not too wide in case your 2D
# spectrum is ever so slightly slanted. For my ASI533MM Pro, a range of 100 px
# centered on the sensor works well, hence these default values:
#
x0, x1 = 1500, 1600

# What part of the image around the 2D spectrum should we ignore when computing
# the mean background value? Which part of the image around the 2D spectrum
# should we use to fit a Gaussian curve? This is parameterized by bin_size,
# which is expressed in pixels. If bin_size is 20, the signal part of the image
# will be +20px / -20px around the spectrum, for a total window height of 40px.
#
#  ////////////////////////////////////////////
#  ///////////// background sky ///////////////
#  -------------------------------------------- <- y0 - bin_size
#
#
#  ******************************************** <- 2D spectrum (y0)
#
#
#  -------------------------------------------- <- y0 + bin_size
#  ///////////// background sky ///////////////
#  ////////////////////////////////////////////
#
bin_size = 30

# Image scale in arcsecond per pixel, used only for display purposes.
image_scale = 0.89

### END PARAMETERS BLOCK ######################################################

dir = sys.argv[1] if len(sys.argv) > 1 else '.'

if not path.isdir(dir):
  sys.exit(f"{dir} does not seem to be a valid directory.")

def measure_new_image(event):
  # Load the image data - TODO: add try/except
  image = fits.open(event.src_path)
  imageData = image[0].data
  imageHeader = image[0].header

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
  background = np.concatenate((values[ : maxIndex-bin_size], values[maxIndex + bin_size : ]))
  backgroundValue = np.mean(background, axis=0)
  # print(f"Background value is {backgroundValue}")

  # Subtract the background
  values = np.subtract(values, backgroundValue)

  # Get the maximum value:
  maxValue = values[maxIndex]

  # Extract the useful part of the image, the one that contains only the 2D spectrum
  spectrum = values[maxIndex - bin_size : maxIndex + bin_size]

  # Define model function to be used to fit to the data above:
  def gauss(x, *p):
    A, mu, sigma = p
    return A*np.exp(-(x-mu)**2/(2.*sigma**2))

  xdata = np.arange(0, len(values))

  # plt.subplot(3, 1, 2)
  # plt.scatter(xdata, spectrum)

  # p0 is the initial guess for the fitting coefficients (A, mu and sigma above)
  p0 = [maxValue, maxIndex, 3]

  coeff, var_matrix = curve_fit(gauss, xdata, values, p0=p0)
  A, mu, sigma = coeff

  # Compute a normalized value of the overall amount of signal. Indeed, due to
  # aberrations, e.g., astigmatism, a lower FWHM image is not guaranteed to
  # have the highest SNR, so we will display both to the user.
  normalizedSignalValue = 0.
  if "EXPTIME" in imageHeader:
    exptime = imageHeader["EXPTIME"]
    if exptime > 0:
      normalizedSignalValue = np.sum(spectrum)/exptime

  # fitted_gaussian_curve = gauss(xdata, *coeff)
  # plt.subplot(3, 1, 3)
  # plt.plot(xdata, fitted_gaussian_curve, label='Fitted curve')
  # plt.show()

  filename = path.basename(event.src_path)
  print(f"{filename}: FWHM = {sigma * 2:.2f}px -> {sigma * 2 * image_scale:.2f}\" | NSIG = {normalizedSignalValue:.2f}")

event_handler = PatternMatchingEventHandler(patterns=["*.fit", "*.fits"], ignore_directories=True)
event_handler.on_created = measure_new_image

observer = Observer()
observer.schedule(event_handler, dir, recursive=False)
observer.start()

print(f"Watching directory {dir}\nPress 'q' to exit")

key = getkey()
if key == 'q':
  observer.stop()
  observer.join()
