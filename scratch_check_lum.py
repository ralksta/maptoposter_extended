from PIL import Image
import numpy as np

def mean_lum(path):
    img = Image.open(path).convert('L')
    return np.mean(np.array(img))

print("Original:", mean_lum('posters/kada_ralf2_landscape-plaque_20260517_200143.png'))
print("M1:", mean_lum('scratch/test_texture_multiply.png'))
print("M2 (bright):", mean_lum('scratch/test_texture_multiply_bright.png'))
print("M3 (gray bright):", mean_lum('scratch/test_texture_multiply_gray.png'))
