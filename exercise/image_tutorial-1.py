import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
img = mpimg.imread('temp.jpg')
imgplot = plt.imshow(img)
plt.colorbar()
plt.show()
