import os
from flask import Flask, request, send_file, after_this_request

from src.cropper import ImageCropper


app = Flask(__name__)


@app.route("/date/<int:date>/crop_by_bounding_box")
def get_crop_by_bounding_box(date: int):
    min_x = request.args.get('min_x', type=float)
    max_x = request.args.get('max_x', type=float)
    min_y = request.args.get('min_y', type=float)
    max_y = request.args.get('max_y', type=float)

    with ImageCropper(date=date, min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y) as cropper:
        image_name, image_path = cropper.crop_image_by_bounding_box()

    @after_this_request
    def remove_file(response):
        os.remove(image_path)
        return response

    return send_file(image_name, as_attachment=True)


@app.route("/date/<int:date>/crop_by_geojson", methods=['POST'])
def get_crop_by_geojson(date: int):
    data = request.data.decode('utf-8')
    with ImageCropper(date=date) as cropper:
        image_name, image_path = cropper.crop_image_by_geojson(geo_json_str=data)

    @after_this_request
    def remove_file(response):
        os.remove(image_path)
        return response

    return send_file(image_name, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
