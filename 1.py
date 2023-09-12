import rasterio

with rasterio.open("mytiff/shard_0.tif") as sar_ds:
    print(sar_ds.width, sar_ds.height)   #输出Tif的长宽
    print(sar_ds.crs)                    #坐标参考系
    print(sar_ds.transform)              #反射变化参数
    print(sar_ds.count)                  #波段数目
    print(sar_ds.indexes)
    print(sar_ds.meta)
    print(sar_ds.xy(0,0))


print("--------------------------")

with rasterio.open("subset_0_of_VH.tif") as sar_ds:
    print(sar_ds.width, sar_ds.height)  # 输出Tif的长宽
    print(sar_ds.crs)  # 坐标参考系
    print(sar_ds.transform)  # 反射变化参数
    print(sar_ds.count)  # 波段数目
    print(sar_ds.indexes)
    print(sar_ds.meta)
    print(sar_ds.xy(0,0))

file_path = r'D:\zhuomian\My_project\yoloair-iscyy-beta\data\images\shard_234.jpg'
start_index = file_path.rfind('\\') + 1
end_index = file_path.rfind('.')
file_name = file_path[start_index:end_index]
print(file_name)  # Output: shard_234

