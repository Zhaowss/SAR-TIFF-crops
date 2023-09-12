import cv2
from matplotlib import pyplot as plt

# 读取tif图像
image_path = 'mytiff/shard_235.tif'
tif_image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
print(tif_image.dtype)
tif_image = tif_image.astype('uint8')  # 或者使用其他正确的数据类型
print(tif_image.dtype)

# 线性拉伸像素值范围
min_val = tif_image.min()
max_val = tif_image.max()
tif_image = 255 * (tif_image - min_val) / (max_val - min_val)
tif_image = tif_image.astype('uint8')

# 直方图均衡化
equalized_image = cv2.equalizeHist(tif_image)

# 检查是否成功读取图像
if tif_image is None:
    print("无法读取图像")
else:
    # 可视化图像
    plt.imshow(tif_image, cmap='gray')  # 如果是灰度图，请使用'gray' colormap
    plt.axis('off')  # 关闭坐标轴
    plt.show()
