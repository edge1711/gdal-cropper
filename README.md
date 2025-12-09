## How to Run

### Using Docker

1. Build the Docker image:
```bash
docker build -t cropper .
```

2. Run the container:
```bash
docker run -d --rm -p 5000:5000 cropper
```

The application will be available at `http://localhost:5000`

3. Make requests to the API:

**Crop by Bounding Box:**
```bash
curl "http://localhost:5000/date/20160501/crop_by_bounding_box?min_x=27.37&max_x=27.42&min_y=44.15&max_y=44.20" \
  -o cropped_image.tif
```

**Crop by GeoJSON:**
```bash
curl -X POST "http://localhost:5000/date/20160501/crop_by_geojson" -H "Content-Type: application/json" -d '{"type":"Feature","properties":{"id":1},"geometry":{"type":"Multipolygon","coordinates":[[[[27.397511483867362,44.161117466010516],[27.393924221672666,44.159751598403503],[27.393556666460618,44.159252063395591],[27.393726740035870,44.158373985750522],[27.392040835956994,44.157378400690988],[27.390354358253163,44.156239034941315],[27.390977924658255,44.152849194060536],[27.391438333095618,44.149298658002031],[27.386781918912796,44.147461728155896],[27.384487250437232,44.146859408403664],[27.382636468741264,44.156671855578281],[27.383891699721374,44.156645049015140],[27.384649769913505,44.157388133683327],[27.385547083122507,44.160232076255667],[27.387997850095061,44.160722084482430],[27.390672446485077,44.161638147279866],[27.395361188085396,44.163429614137918],[27.396513835695238,44.162325787855522],[27.397511483867362,44.161117466010516]]]]}}'  \
-o cropped_image.tif

```


**Parameters:**
- `date`: Integer date value (e.g., 20160501)
- `min_x`, `max_x`, `min_y`, `max_y`: Bounding box coordinates (floats)
- GeoJSON: Valid GeoJSON geometry in the request body