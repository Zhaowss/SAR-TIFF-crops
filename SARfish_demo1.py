import numpy
import pandas as pd
from PIL import Image

import torch
import torchvision
from torchvision import transforms

import os
import shutil
import numpy as np

from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from shapely import geometry

import glob
from tqdm import tqdm
import rasterio
from rasterio.mask import mask

import pickle
import sys
import osgeo.gdal as gdal
import geopandas as gpd
from osgeo import osr
from shapely.geometry import Point
from geopandas import GeoDataFrame



#define functions

def get_instance_segmentation_model(num_classes):
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
    return model


def prepare_image(image_path):
  im = Image.open(image_path)
  jpg_path = image_path[:-4]+".jpg"
  # print(jpg_path)
  im.save(jpg_path)
  img = Image.open(jpg_path).convert("RGB")
  img_transforms = transforms.Compose([
                                      transforms.Resize((800,800)),
                                      transforms.ToTensor(),
                                      transforms.Normalize(mean=0.5, std=0.2)
                                      ])
  img = img_transforms(img)
  return img

def get_new_image_detections(image_path, threashold):
  img = prepare_image(image_path)
  with torch.no_grad():
    pred = model_ft(img.unsqueeze(0))
    pred = {key: value.numpy() for key, value in pred[0].items()}
    num_detections = len(pred["scores"])
    high_confidence_detection_numbers = []
    for i in range(num_detections):
      score = pred["scores"][i]
      if score > 0.5:
        high_confidence_detection_numbers.append(i)
    detection_bbox_list = []
    for detection_number in high_confidence_detection_numbers:
      detection_bbox = list(pred["boxes"][detection_number])
      detection_bbox_list.append(detection_bbox)
    # display_img = read_image(image_path)
    boxes = torch.tensor(detection_bbox_list, dtype=torch.float)
    print(boxes)
    colors = ["green"]*len(detection_bbox_list)
    result = draw_bounding_boxes(img, boxes, colors=colors, width=2)
    return result

# plt.rcParams["savefig.bbox"] = 'tight'


# def show(imgs):
#     if not isinstance(imgs, list):
#         imgs = [imgs]
#     fig, axs = plt.subplots(ncols=len(imgs), squeeze=False, figsize=(24, 24))
#     for i, img in enumerate(imgs):
#         img = img.detach()
#         img = F.to_pil_image(img)
#         axs[0, i].imshow(np.asarray(img))
#         axs[0, i].set(xticklabels=[], yticklabels=[], xticks=[], yticks=[])


# Takes a Rasterio dataset and splits it into squares of dimensions squareDim * squareDim
def splitImageIntoCells(img, filename, squareDim, shard_dir):
    # numberOfCellsWide 和 numberOfCellsHigh：这两行代码计算图像可以被分割成多少个水平方向（numberOfCellsWide）
    # 和垂直方向（numberOfCellsHigh）的小方块。这里通过将图像的宽度和高度除以 squareDim 来计算。
    numberOfCellsWide = img.shape[1] // squareDim
    numberOfCellsHigh = img.shape[0] // squareDim

    x, y = 0, 0
    count = 0
    for hc in range(numberOfCellsHigh):
        y = hc * squareDim
        for wc in range(numberOfCellsWide):
            x = wc * squareDim
            geom = getTileGeom(img.transform, x, y, squareDim)
            getCellFromGeom(img, geom, filename, count, shard_dir)
            count = count + 1

# Generate a bounding box from the pixel-wise coordinates using the original datasets transform property
def getTileGeom(transform, x, y, squareDim):
    # 将确定的点映射到指定的坐标系中形成一个方框
    corner1 = (x, y) * transform
    corner2 = (x + squareDim, y + squareDim) * transform
    return geometry.box(corner1[0], corner1[1],
                        corner2[0], corner2[1])

# Crop the dataset using the generated box and write it out as a GeoTIFF
def getCellFromGeom(img, geom, filename, count, shard_dir):
    crop, cropTransform = mask(img, [geom], crop=True)
    writeImageAsGeoTIFF(crop,
                        cropTransform,
                        img.meta,
                        img.crs,
                        filename+"_"+str(count), shard_dir)

# Write the passed in dataset as a GeoTIFF
def writeImageAsGeoTIFF(img, transform, metadata, crs, filename, shard_dir):
    metadata.update({"driver":"GTiff",
                     "height":img.shape[1],
                     "width":img.shape[2],
                     "transform": transform,
                     "crs": crs})
    with rasterio.open(shard_dir+filename+".png", "w", **metadata) as dest:
        dest.write(img)

def get_new_image_detection_coords(image_path, threashold):
  img = prepare_image(image_path)
  # 将图像处理成一个可以传入网络的tensor,然后再将其处理成可以使用的指定的像素的图像
  # 其实就是预处理部分之后将其作为传入
  with torch.no_grad():
    #   扩增通道的维度送入图像中检测
    pred = model_ft(img.unsqueeze(0))
    pred = {key: value.numpy() for key, value in pred[0].items()}
    num_detections = len(pred["scores"])
    high_confidence_detection_numbers = []
    for i in range(num_detections):
      score = pred["scores"][i]
      if score > 0.5:
        high_confidence_detection_numbers.append(i)
    detection_bbox_list = []
    for detection_number in high_confidence_detection_numbers:
      detection_bbox = list(pred["boxes"][detection_number])
      detection_bbox_list.append(detection_bbox)
    # display_img = read_image(image_path)
    return detection_bbox_list

def get_new_image_detection_coords_and_prediction_confidence(image_path, threashold):
  # 传入的参数 式我们的图像的路径
  # 传入图像的置信度的阈值，过滤低置信度的目标

  img = prepare_image(image_path)
  with torch.no_grad():
    pred = model_ft(img.unsqueeze(0))
    pred = {key: value.numpy() for key, value in pred[0].items()}
    num_detections = len(pred["scores"])
    high_confidence_detection_numbers = []
    for i in range(num_detections):
      score = pred["scores"][i]
      # print(score)
      if score > threashold:
        high_confidence_detection_numbers.append((i, score))
    detection_bbox_list = []
    for detection_number in high_confidence_detection_numbers:
      detection_bbox = list(pred["boxes"][detection_number[0]])
      detection_bbox_list.append((detection_number[1], detection_bbox))
    # display_img = read_image(image_path)
    return detection_bbox_list

def pixel2coord(img_path, x, y):
    """
    Returns latitude/longitude coordinates from pixel x, y coords

    Keyword Args:
      img_path: Text, path to tif image
      x: Pixel x coordinates. For example, if numpy array, this is the column index
      y: Pixel y coordinates. For example, if numpy array, this is the row index
    """
    # Open tif file
    ds = gdal.Open(img_path)

    old_cs = osr.SpatialReference()
    old_cs.ImportFromWkt(ds.GetProjectionRef())

    # create the new coordinate system
    # In this case, we'll use WGS 84
    # This is necessary becuase Planet Imagery is default in UTM (Zone 15). So we want to convert to latitude/longitude
    wgs84_wkt = """
    GEOGCS["WGS 84",
        DATUM["WGS_1984",
            SPHEROID["WGS 84",6378137,298.257223563,
                AUTHORITY["EPSG","7030"]],
            AUTHORITY["EPSG","6326"]],
        PRIMEM["Greenwich",0,
            AUTHORITY["EPSG","8901"]],
        UNIT["degree",0.01745329251994328,
            AUTHORITY["EPSG","9122"]],
        AUTHORITY["EPSG","4326"]]"""
    new_cs = osr.SpatialReference()
    new_cs.ImportFromWkt(wgs84_wkt)

    # create a transform object to convert between coordinate systems
    transform = osr.CoordinateTransformation(old_cs,new_cs)

    gt = ds.GetGeoTransform()

    # GDAL affine transform parameters, According to gdal documentation xoff/yoff are image left corner, a/e are pixel wight/height and b/d is rotation and is zero if image is north up.
    xoff, a, b, yoff, d, e = gt

    xp = a * x + b * y + xoff
    yp = d * x + e * y + yoff

    lat_lon = transform.TransformPoint(xp, yp)

    xp = lat_lon[0]
    yp = lat_lon[1]

    return (xp, yp)


def find_img_coordinates(img_array, image_filename):
    img_coordinates = np.zeros((img_array.shape[0], img_array.shape[1], 2)).tolist()
    for row in range(0, img_array.shape[0]):
        for col in range(0, img_array.shape[1]):
            img_coordinates[row][col] = Point(pixel2coord(img_path=image_filename, x=col, y=row))
    return img_coordinates


def find_image_pixel_lat_lon_coord(image_filenames, output_filename):
    """
    Find latitude, longitude coordinates for each pixel in the image

    Keyword Args:
      image_filenames: A list of paths to tif images
      output_filename: A string specifying the output filename of a pickle file to store results

    Returns image_coordinates_dict whose keys are filenames and values are an array of the same shape as the image with each element being the latitude/longitude coordinates.
    """
    image_coordinates_dict = {}
    for image_filename in image_filenames:
        print('Processing {}'.format(image_filename))
        img = Image.open(image_filename)
        img_array = np.array(img)
        img_coordinates = find_img_coordinates(img_array=img_array, image_filename=image_filename)
        image_coordinates_dict[image_filename] = img_coordinates
        with open(os.path.join(DATA_DIR, 'interim', output_filename + '.pkl'), 'wb') as f:
            pickle.dump(image_coordinates_dict, f)
    return image_coordinates_dict

# def get_detections(image_path):
#   coord_list = get_new_image_detection_coords(image_path, 0.5)
#   detections_lat_lon = pixel_bb_to_coord_bb(coord_list, image_path)
#   return detections_lat_lon

def pixel_bb_to_coord_bb(xy_coord_list, image_path):
  detection_list = []
  for xy_bb in xy_coord_list:
    # print(xy_bb)
    x1 = xy_bb[0]
    y1 = xy_bb[1]
    x2 = xy_bb[2]
    y2 = xy_bb[3]
    xy_cords = (x1,x2,y1,y2)
    centerx, centery = (numpy.average(xy_cords[:2]),numpy.average(xy_cords[2:]))
    # print(centerx, centery)
    lat_lon_detection = pixel2coord(image_path, centerx, centery)
    # print(lat_lon_detection)
    detection_list.append(lat_lon_detection)
  return detection_list

# def plot_detections(tiff_path, shard_dir, outpath):
#   with rasterio.open(tiff_path) as src:
#   	print("Splitting image into shards")
#   	splitImageIntoCells(src, "shard", 800, shard_dir)
#   shard_list = glob.glob(shard_dir+"*.png")
#   list_of_ship_detections = []
#   for image_fp in tqdm(shard_list):
#     im = Image.open(image_fp).convert('RGB')
#     jpg_path = image_fp[:-4]+".jpg"
#     # print(jpg_path)
#     # im.mode = 'I'
#     # im.point(lambda i:i*(1./256)).convert('L').save(jpg_path)
#     im.save(jpg_path)
#     coords = get_new_image_detection_coords(jpg_path, 0.1)
#     detections_lat_lon = pixel_bb_to_coord_bb(coords, image_fp)
#     list_of_ship_detections.append(detections_lat_lon)
#   with rasterio.open(tiff_path) as src:
#       boundary = src.bounds
#       img = src.read()
#       nodata = src.nodata
#   print(list_of_ship_detections)
#   # mapit = folium.Map( location=[list_of_ship_detections[0][0][1],list_of_ship_detections[0][0][0]], zoom_start=11 )
#   mapit = folium.Map(location = [45.749692, 31.922025], zoom_start = 9)
#   folium.raster_layers.ImageOverlay(
#       image=img[0],
#       name='SAR_Image',
#       opacity=1,
#       bounds= [[boundary.bottom, boundary.left], [boundary.top, boundary.right]]
#   ).add_to(mapit)
#   for image_list in list_of_ship_detections:
#     for detection_coord in image_list:
#       folium.Circle(radius=100,location=[ detection_coord[1], detection_coord[0] ],color='green',fill=False,).add_to(mapit)
#   mapit.save(outpath)
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_bounding_boxes(image, boxes, labels=None, save_path=None):
    """
    Draw bounding boxes on an image and optionally save it to a specified path.

    Parameters:
        image (numpy array): The image to draw bounding boxes on.
        boxes (list of tuples): List of tuples representing bounding boxes. Each tuple should be in the format (x, y, width, height).
        labels (list, optional): List of strings representing labels for each bounding box. Default is None.
        save_path (str, optional): The path where to save the image with bounding boxes. If not provided, the image will be displayed but not saved. Default is None.

    Returns:
        None (displays the image with bounding boxes) or saves the image to the specified path.
    """
    fig, ax = plt.subplots(1)
    ax.imshow(image)
    for box in boxes:
        print(box)
        x_min, y_min, x_max, y_max = box[0],box[1],box[2],box[3]
        width = x_max - x_min
        height = y_max - y_min
        rect = patches.Rectangle((x_min, y_min), width, height, linewidth=1, edgecolor='r', facecolor='none')
        ax.add_patch(rect)
    if save_path is not None:
        plt.savefig(save_path)
        plt.close()  # Close the figure to release memory
    else:
        plt.show()





def get_geojson_detections(tiff_path, shard_dir, outpath):
  with rasterio.open(tiff_path) as src:
      # 打开原始的TIFF的图像
  	print("Splitting image into shards")
      # 开始裁剪成指定的尺寸的图像
      # 打印文件的保存的地址
  	print(shard_dir)
      # 调用裁剪图像，将原始的SAR图像信息裁剪800*800的图像，并且
  	splitImageIntoCells(src, "shard", 800, shard_dir)
  # 得到我们已经裁剪好的图像的
  shard_list = glob.glob(shard_dir+"*.png")
  # 创建一个列表数组保存我们的船舶的检测的结果
  list_of_ship_detections = []
  # 保存我们的检测的结果的置信度
  confidence_list = []
  # 开始检测船舶的数据
  print("Finding ships")
  for image_fp in tqdm(shard_list):
    im = Image.open(image_fp).convert('RGB')
    jpg_path = image_fp[:-4]+".jpg"
    # print(jpg_path)
    # im.mode = 'I'
    # im.point(lambda i:i*(1./256)).convert('L').save(jpg_path)
    im.save(jpg_path)
    # 保存图片为jpg的格式
    confidence_and_coords = get_new_image_detection_coords_and_prediction_confidence(jpg_path, detection_threshold)
    # detection_bbox_list得到检测目标的bbox

    print(confidence_and_coords)
    coords_list = []

    for tuple_value in confidence_and_coords:
    	coords_list.append(tuple_value[1])
        # 检测出的船舶的而目标的框 的像素的位置
    	confidence_list.append(tuple_value[0])
    # 像素位置的转换
    print(coords_list)
    if coords_list:
      draw_bounding_boxes(im, coords_list, labels=None, save_path=image_fp[:-4]+"_detect_"+ ".jpg")

    detections_lat_lon = pixel_bb_to_coord_bb(coords_list, image_fp)
    list_of_ship_detections.append(detections_lat_lon)
  df = pd.DataFrame(columns = ["lat","lon"])
  i = 0
  flat_list = [item for sublist in list_of_ship_detections for item in sublist]
  for shard in list_of_ship_detections:
    for detection in shard:
      if detection[0] is not None:
      	lon = detection[0]
      if detection[1] is not None:
      	lat = detection[1]
      df.loc[i, "lon"] = lon
      df.loc[i, "lat"] = lat
      i = i+1
  geometry = [Point(xy) for xy in zip(df.lon, df.lat)]
  df.to_csv("myresult.csv")
  df = df.drop(['lon', 'lat'], axis=1)
  gdf = GeoDataFrame(df, crs="EPSG:4326", geometry=geometry)
  world_land_map = gpd.read_file(rootdir+"/"+"world_land_areas.geojson")
  intersections = gdf.intersects(world_land_map.unary_union)
  # print(confidence_list)
  gdf["onshore_detection"] = list(intersections)
  gdf["detection_confidence"] = confidence_list
  gdf.to_file(outpath, driver='GeoJSON')

tiff_filename = sys.argv[1]
output_geojson_filename = sys.argv[2]
detection_threshold = float(sys.argv[3])

rootdir = os.getcwd()
shard_dir = rootdir+"/shards/"
tiff_filepath = rootdir+"/"+tiff_filename
output_geojson_filepath = rootdir+"/" + output_geojson_filename


os.makedirs(shard_dir, exist_ok=True)

num_classes = 2
model_ft = get_instance_segmentation_model(num_classes)
model_ft.load_state_dict(torch.load(rootdir+"/"+"model.bin", map_location=torch.device('cpu')))
model_ft.eval()

get_geojson_detections(tiff_filepath, shard_dir, output_geojson_filepath)
shutil.rmtree(shard_dir)



# python SARfish_demo1.py subset_0_of_VH.tif detections1.geojson 0.5