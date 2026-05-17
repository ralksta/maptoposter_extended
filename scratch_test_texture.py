from PIL import Image, ImageChops, ImageEnhance

base_img = Image.open('posters/kada_ralf2_landscape-plaque_20260517_200143.png').convert('RGB')
texture_img = Image.open('assets/paper_texture.png').convert('RGB')
texture_img = texture_img.resize(base_img.size, Image.Resampling.LANCZOS)

# Method 1: Direct multiply
m1 = ImageChops.multiply(base_img, texture_img)
m1.save('scratch/test_texture_multiply.png')

# Method 2: Multiply with brightened texture
enhancer = ImageEnhance.Brightness(texture_img)
t2 = enhancer.enhance(1.2)
m2 = ImageChops.multiply(base_img, t2)
m2.save('scratch/test_texture_multiply_bright.png')

# Method 3: Grayscale multiply
t3 = texture_img.convert('L').convert('RGB')
enhancer = ImageEnhance.Brightness(t3)
t3 = enhancer.enhance(1.1)
m3 = ImageChops.multiply(base_img, t3)
m3.save('scratch/test_texture_multiply_gray.png')

print("Done")
