import os
import json
import ast
from typing import Tuple

from osgeo import gdal, osr, ogr
from osgeo.gdalconst import *


class ImageCropper:

    gdal.UseExceptions()  # remove FutureWarning
    gdal.AllRegister()

    WGS84 = "EPSG:4326"
    SOURCE_FILE_PATH = "./satellite_images/{date}.tif"
    OUTPUT_FILE_NAME_BY_BOUNDING_BOX = "{date}_cutted_by_bounding_box.tif"
    OUTPUT_FILE_NAME_BY_GEO_JSON = "{date}_cutted_by_geojson.tif"
    OUTPUT_PATH = "./your-project/{file_name}"

    def __init__(
            self,
            date: int,
            min_x: float = None,
            max_x: float = None,
            min_y: float = None,
            max_y: float = None
    ) -> None:
        self.date = date
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y

        self.ds: gdal.Dataset = self.get_file_dataset()

        self.geo_transform = self.ds.GetGeoTransform()
        self.origin_x = self.geo_transform[0]
        self.origin_y = self.geo_transform[3]
        self.pixel_width = self.geo_transform[1]
        self.pixel_height = self.geo_transform[5]
        self.row_rotation = self.geo_transform[2]
        self.column_rotation = self.geo_transform[4]

        self.projection = self.ds.GetProjection()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ds.Close()

    def get_file_dataset(self) -> gdal.Dataset:
        file_path = self.SOURCE_FILE_PATH.format(date=self.date)

        if os.path.isfile(file_path):
            ds = gdal.Open(file_path, GA_ReadOnly)
            return ds
        else:
            raise FileNotFoundError

    def create_transformation(self, is_geo_json=False) -> osr.CoordinateTransformation:
        source_srs = osr.SpatialReference()
        source_srs.SetFromUserInput(self.WGS84)

        target_srs = osr.SpatialReference()
        target_srs.ImportFromWkt(self.projection)

        if is_geo_json:
            source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            target_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

        transform = osr.CoordinateTransformation(source_srs, target_srs)

        return transform

    def convert_coordinates(self, lat: float, long: float) -> Tuple[float, float]:
        transform = self.create_transformation()
        transformed_coordinates = transform.TransformPoint(lat, long)
        x, y, _ = transformed_coordinates

        return x, y

    def convert_to_pixel(self, x: float, y: float) -> Tuple[float, float]:
        x_offset = int((x - self.origin_x) / self.pixel_width)
        y_offset = int((y - self.origin_y) / self.pixel_height)

        return x_offset, y_offset

    def crop_image_by_bounding_box(self) -> Tuple[str, str]:
        output_file_name = self.OUTPUT_FILE_NAME_BY_BOUNDING_BOX.format(date=str(self.date))
        output_path = self.OUTPUT_PATH.format(file_name=output_file_name)

        x_min_coord, y_max_coord = self.convert_coordinates(lat=self.max_y, long=self.min_x)
        x_max_coord, y_min_coord = self.convert_coordinates(lat=self.min_y, long=self.max_x)

        x_min_offset, y_min_offset = self.convert_to_pixel(x=x_min_coord, y=y_max_coord)
        x_max_offset, y_max_offset = self.convert_to_pixel(x=x_max_coord, y=y_min_coord)

        width = x_max_offset - x_min_offset
        height = y_max_offset - y_min_offset

        offsets = tuple(
            self.ds.GetRasterBand(n).ReadAsArray(x_min_offset, y_min_offset, width, height)
            for n in range(1, self.ds.RasterCount + 1)
        )

        driver: gdal.Driver = self.ds.GetDriver()

        out_dataset: gdal.Dataset = driver.Create(
            output_path,
            width,
            height,
            self.ds.RasterCount,
            self.ds.GetRasterBand(1).DataType
        )

        new_origin_x = self.origin_x + x_min_offset * self.pixel_width
        new_origin_y = self.origin_y + y_min_offset * self.pixel_height

        new_geo_transform = (
            new_origin_x,
            self.pixel_width,
            self.row_rotation,
            new_origin_y,
            self.column_rotation,
            self.pixel_height
        )

        out_dataset.SetGeoTransform(new_geo_transform)
        out_dataset.SetProjection(self.projection)

        for n, offset in enumerate(offsets, start=1):
            out_band = out_dataset.GetRasterBand(n)
            out_band.WriteArray(offset)

            source_nodata = self.ds.GetRasterBand(n).GetNoDataValue()

            if source_nodata is not None:
                out_band.SetNoDataValue(source_nodata)

            out_band.FlushCache()
            out_band.GetStatistics(0, 1)

        return output_file_name, output_path

    def crop_image_by_geojson(self, geo_json_str: str) -> Tuple[str, str]:
        output_file_name = self.OUTPUT_FILE_NAME_BY_GEO_JSON.format(date=str(self.date))
        output_path = self.OUTPUT_PATH.format(file_name=output_file_name)

        geo_json_dict = ast.literal_eval(geo_json_str)
        geo_coordinates = json.dumps(geo_json_dict.get('geometry'))
        ogr_geom: ogr.Geometry = ogr.CreateGeometryFromJson(geo_coordinates)
        transform: osr.CoordinateTransformation = self.create_transformation(is_geo_json=True)
        ogr_geom.Transform(transform)

        min_x, max_x, min_y, max_y = ogr_geom.GetEnvelope()
        x_min_offset, y_min_offset = self.convert_to_pixel(x=min_x, y=max_y)
        x_max_offset, y_max_offset = self.convert_to_pixel(x=max_x, y=min_y)

        width = x_max_offset - x_min_offset
        height = y_max_offset - y_min_offset

        mem_driver: gdal.Driver = gdal.GetDriverByName('MEM')
        ds_mask: gdal.Dataset = mem_driver.Create('', width, height, 1, gdal.GDT_Byte)

        mask_origin_x = self.origin_x + x_min_offset * self.pixel_width
        mask_origin_y = self.origin_y + y_min_offset * self.pixel_height

        mask_geo_transform = (
            mask_origin_x,
            self.pixel_width,
            0,
            mask_origin_y,
            0,
            self.pixel_height
        )

        ds_mask.SetGeoTransform(mask_geo_transform)
        ds_mask.SetProjection(self.projection)

        mem_ogr_driver: gdal.Driver = ogr.GetDriverByName('Memory')
        mem_ogr_ds: gdal.DataSource = mem_ogr_driver.CreateDataSource('memData')

        srs: osr.SpatialReference = osr.SpatialReference()
        srs.ImportFromWkt(self.projection)

        mem_layer: gdal.RasterizeLayer = mem_ogr_ds.CreateLayer('geometry', srs, ogr.wkbPolygon)

        feature_defn: ogr.Feature = mem_layer.GetLayerDefn()
        feature: ogr.Feature = ogr.Feature(feature_defn)
        feature.SetGeometry(ogr_geom)
        mem_layer.CreateFeature(feature)

        gdal.RasterizeLayer(
            ds_mask,
            [1],
            mem_layer,
            burn_values=[1],
            options=["ALL_TOUCHED=FALSE"]
        )

        mask_band = ds_mask.GetRasterBand(1)
        mask = mask_band.ReadAsArray()

        bands_data= []
        for i in range(1, self.ds.RasterCount + 1):
            band = self.ds.GetRasterBand(i)
            data = band.ReadAsArray(x_min_offset, y_min_offset, width, height)

            masked_data = data * mask
            bands_data.append(masked_data)

        driver = gdal.GetDriverByName('GTiff')
        out_dataset = driver.Create(
            output_path,
            width,
            height,
            self.ds.RasterCount,
            self.ds.GetRasterBand(1).DataType
        )

        new_origin_x = self.origin_x + x_min_offset * self.pixel_width
        new_origin_y = self.origin_y + y_min_offset * self.pixel_height

        new_geo_transform = (
            new_origin_x,
            self.pixel_width,
            self.row_rotation,
            new_origin_y,
            self.column_rotation,
            self.pixel_height
        )

        out_dataset.SetGeoTransform(new_geo_transform)
        out_dataset.SetProjection(self.projection)

        for i in range(1, self.ds.RasterCount + 1):
            out_band = out_dataset.GetRasterBand(i)
            out_band.WriteArray(bands_data[i - 1])

            source_nodata = self.ds.GetRasterBand(i).GetNoDataValue()
            if source_nodata is not None:
                out_band.SetNoDataValue(source_nodata)

        out_dataset.FlushCache()

        return output_file_name, output_path


if __name__ == "__main__":
    date_ = 20160501
    min_x_ = 27.37
    max_x_ = 27.42
    min_y_ = 44.15
    max_y_ = 44.20

    cropper = ImageCropper(date=date_, min_x=min_x_, max_x=max_x_, min_y=min_y_, max_y=max_y_)

    cropper.crop_image_by_geojson('./examples/input_data/geometry_cut.geojson')
    cropper.crop_image_by_bounding_box()
