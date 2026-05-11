from PIL import Image
import numpy as np

img = Image.open('/home/kevin/Downloads/clustering/F3_test_for_clustering/previews/F3_H1_amp_at_horizon.png')
img = img.convert('RGB')
arr = np.array(img)

print(f"Image shape: {arr.shape}")
reshaped = arr.reshape(-1, 3)
unique_colors, counts = np.unique(reshaped, axis=0, return_counts=True)
sorted_idx = np.argsort(counts)[::-1]

print("Top 10 colors (RGB):")
for i in range(10):
    print(unique_colors[sorted_idx[i]])
    
max_r = unique_colors[np.argmax(unique_colors[:, 0])]
max_b = unique_colors[np.argmax(unique_colors[:, 2])]
print(f"Max Red pixel: {max_r}")
print(f"Max Blue pixel: {max_b}")
