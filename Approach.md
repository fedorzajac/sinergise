Upon reading the task twice (to understand :D ) I will now try to summarize my thoughts

1. pipeline written in python

    a. Goal

      - this will probably be used for airflow
      - what does syntesis product means in this scope? (GPT helps, or Gemini or Copilot or Claude, or all of them)
      - dekadal NDVI composide product
      - irregural revisits -> interpolation method (no idea what that is, GPT helps)
      -  data for 1st, 11th, 21st.

    b. Bonus

      -  (opt) fill remaining data from CLMS 300m, resample to match sentines-2 grid (probably with rasterio.)

    c. Input

     - so probably CLI tool (or script that will accept arguments) (I remember some example code at cdse example page on how to utilize data, or somewhere.)

    d. Output

    - structure of my choice.
    - read me instruction on how to run/use.

2. BYOC Architecture Design

   - ok, I will check docs and will have to figure out what is it about, GPT helps.

  a. Scenario

  - 50TB archive...
  - So, I have no idea, but my think on that is this:
  - Onboarding - download/gather only requested data and save them. if already present in the archive (or maybe available by recalculation), serve them (or check if newer are present - (or maybe if they are present in other archives of other customers ??? :) to minimize calls ) - will have to check with GPT later.
  - oh and the data should be checked for simultaneous requests... and maybe rate limiting... but it is a pipeline... hmmm.
  - and maybe of course some sanity checks...
  - asumming that all access is provided.

  b. output workflow...

  - are the data present somewhere? yes/no can be recalculated? (this will need some aditional db or something which will handle available areas and cross checks them) yes/no are newer data available? yes/no -> serve saved data / download newest data and save and serve them.
  - maybe I am wrong. I will check later.

.1h

Thursday: Get familiar with terms etc.
did a bit of googling to find:
https://documentation.dataspace.copernicus.eu/notebook-samples/openeo/NDVI_Timeseries.html
and https://registry.opendata.aws/sentinel-2-l2a-cogs/

Sentinel 2 data L2A
so it is probably this:
https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process/Examples/S2L2A.html#all-s2l2a-raw-bands-original-data-no-harmonization

hmm at this point I am at loss on how to get data for polygon instead of bounding box, so maybe just convert it to bounding box? like enclose the polygon in the rectangle... turning to gpt.
oh, I found it in the docs...

so I got the error:
```bash
{"error":{"status":400,"reason":"Bad Request","message":"Your request of 26090.88 meters per pixel exceeds the limit 1500.00 meters per pixel of the collection S2L2A. Please revise the resolution (or corresponding width/height) to make sure it is in supported range.","code":"COMMON_EXCEPTION"}}
```
:D
after a little bit of chatting with gpt I figured out that I cant use polygon directly but I have to reproject or create bounding box in meters via CRS and also it depends on area -> N/S hemisphere, and detecting UTM zone
```python
zone_number = floor((longitude + 180) / 6) + 1
```
so the steps will be: read geojson -> convert to UTM geometry with geopandas.

zone are 6 degrees, else it should be splitted into multiple zones


finally getting towards some results.
I did manage to convert lon/lat into utm and send a request to copernicus., however, I cant manage to get to 10m resolution...
```bash
{"error":{"status":400,"reason":"Bad Request","message":"`width = 2624`, calculated from resx, is larger than allowed 2500.\n","code":"COMMON_BAD_PAYLOAD","errors":[{"parameter":"output->resx","violation":"`width = 2624`, calculated from resx, is larger than allowed 2500."}]}}
```
so I have to choose strategy. I have no idea what to do, checking with gpt.
gpt suggesting get smaller resolution, resample later... hmm.
other possibility is to split  into two segments. hmm.
ok, resize later.
so I am removing resx/y

hurray, I got an image.

squished.

lets resize. as I have no idea how, gpt helps.

ok. So I can get 1 image for start and end date.

lets move on the dekadal grid.

chatting with gpt revealed that I need to figure out passing dates and then there are several approaches on how to calculate missing data.

I decided to try to get a list of dates, when the sentinel passed the area, or basicaly which data are awailable for the AOI.
however, service unavailable: https://sh.dataspace.copernicus.eu/api/v1/catalog/search

So I am trying to mimic the request at postman -> figuring out what is wrong.

ok. I have dekadal dates and was able to get flyover dates from sentinel.

Thinking about it a little bit it is clear that the flyover area may not exactly match for my AOI but lets *assume that the data are perfect in this example*, for the sake of simplicity

GPT suggested that we find nearest date if exact match not exists. from each side (before, after) and we interpolate by date distance from desired date. (NDVI expect also continuous progress or decline).

So I got all the data for the nearest available flyover dates, to download pictures.
I download pictures and.... half of them are ...hmm useless?

So I asked claude to do me an insight (As I have no prior idea about how the picture should actually look like, almost)

hmmm the resized data are lighter, but gpt says that is ok.

I am not doing interpolation yet, I wil try to get also data from other source and then fill NaN gaps in data from sentinel with data from other source:
get data -> resize -> identify NaN -> get data from elsewhere -> resize -> use to fill NaN in resized sentinel data (probably)

docs: https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/clms/bio-geophysical-parameters/vegetation/vegetation-indices/ndvi_global_300m_10daily_v2.html

cool, I got supplemental data, but I got red image after resize... find out that I had to use the second band defined in evalscript.

data ok

now I will try to produce that dekadal images form source data by interpolating images (GPT)

uuuh, hold your chocobos... should I do it maybe on the downloaded data before rescaling? -> smaller image -> less resource usage. No, I will go with the safe path for now.

ok. so the aligned images are almost completly dark :D
but that is ok probably, there were a clouds above.

so now, I also have the supplemental images, which are already aligned, so I will try with help of gpt supplement data for each pixel, retaining NaN if no data available also from supplement.

little stop here, the code look awful now, but I am focusing on having working code, I will refactor later.

ok so last step: fill NaN.

Ah, forgot to mention that I now  work only with already downloaded data to not overwhelm the API, so I have code im separate file. not to mention that I have no tests implemented apart from small sanity checks :D

currently it is now about 10h of work.

YES!

Task 1 almost done.

Now. The code is still in separated fiels, so I have to merge it to one flow.
looks like I would need to use separate directories for data and the DATE information would be crucial piese of information and parameter provided to the function, but that might not be the best approach....

ah yes and the cli must accept only three inputs... so name of the geofile would be also used for naming things, that is ok.

And then I need to do refactoring (code is mess)
And probably I need to do include proper logging
And maybe Objectification of code/methods... ufff. I have to thing what would be the best approach.


Task 1 done.

TODO:
  refactoring:
     - naming, and overall flow
     - error handling and checking, logging
     - generalization, cleanup
     - add tests
     - !parallelization (but I am not sure on python with GIL :/ ?)


## Task 2

Task 2: BYOC Architecture Design
In the role you are applying for, you will frequently use the Sentinel Hub
"Bring Your Own COG" (BYOC) API to onboard custom datasets from
customers or partners. Your prior experience with this specific service is not
expected. Instead, we are interested in assessing your ability to
conceptualise a workflow when presented with an unfamiliar service.
Scenario: A customer wants to make a 50 TB archive of high-resolution
aerial imagery available via the Copernicus Browser. The data is currently
hosted in a private AWS S3 bucket in the us-west-2 region (the CDSE
ecosystem operates on CreoDIAS). Design the workflow (diagram or
detailed step-by-step schematic) describing the steps to onboard this data
efficiently using the Sentinel Hub BYOC API. For this task we suggest
familiarising yourself with the Sentinel Hub BYOC documentation, and
optionally the Python BYOC documentation.
Output: A clear Diagram (using the tools of your choice) OR a structured
Markdown document.

Ok so, part of the process will be involving checks is the data re correct, creating indexes.

I am checking and try to evaluate task 2 with gemini and copilot if I am too much astray. Gemini (as expected) didnt provide meaningful answer, so its copilot show time
-> byoc and amazon s3 is only metadata and indexing and tile service (hmmm)
- well obviously, I didnt read the task carefully, so I started thinking about different concept (professional deformation)

aaaah so that does not mean that I have to fill the 50TB with data, the data are already there, I have to make it available to api. so copilot evaluation:
```bash
🎯 Summary: Are You Far Off?
✔️ Good instincts:

You are thinking in terms of workflow
You consider checking / validation
You consider pipeline concerns

❌ Where you diverged:

BYOC does not involve recalculation or serving logic
No cross-customer storage reuse
No rate limiting
No local caching decisions
No “is data newer” logic
No DB to track reuse

Your design thinking was general-systems-oriented, but BYOC is much simpler and purpose-built.
```

GPT provided different thoughts... but meh.

Basicaly the answer lies in the links provided:

https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Byoc.html
and
the docs from your company: https://sentinelhub-py.readthedocs.io/en/latest/examples/byoc_request.html

so before doing any ingestion, we will need to check all the constrains for tiles and bands, data_names, COG header etc mentioned in the docs.

directly from docs:

*Your data needs to be organized into collections of tiles. Each tile needs to contain a set of bands and (optionally) an acquisition date and time. Tiles with the same bands can be grouped into collections. Think of the Sentinel-2 data source as a collection of Sentinel-2 tiles.*

and I also found this in docs: https://www.youtube.com/watch?v=OGxwRHtn5H8 - General Workflow@3:14 - but we assume that the data are already on amazon s3 bucket.


### Proposed Workflow

1 check data compatibility with sentinel hub, tiles, bands constrains
- constrains and setting in doc
- inspect data in QGIS
2 convert data to COG with GDAL
- make sure you have necessary tools installed (gdal-3)
- remove internal tiff mask if needed
- retiling - conversion for smaller tiles
(gdal example command in docs)
3 create account and bucket in amazon s3
- us-west-2 for US or eu-central for eu (bucket region in docs)
- uniq name
- bucket settings (from docs) permissions, from json from docs, update bucket
- upload tiles
4 create collection and add to dashboard
- create new collection (name, type-byoc, location(asw bucket location))  and bucket name, save
- copy collection ID
- sentinel hub only displays data from that bucket
5 add tile
- tile, add tile
- copy s3 url from bucket (21:21) - rename file for default bands
- one by one (:D)
- note on naming (23:45)
- deleting file on bucket, must be deleted from sentinel hub as well/ or reingest
- bands naming
6 Request in sentinel hub
- set time in time range
- set evalscript
- set correct values (0-255 to 0-1 = RGB/255)
- set bouding box
- test request
- set mask for no data value in dashboard (30:00)
- additional cover geometry (docs), cover geometry editor
7 process API request
- new configuration, configuration utility, new layer - source and collection -BYOC Collection ID from AWS (33:38)
- copy evalscript, save
- EO brovser -> sensing time -> click visualise
8 QGIS
- sentinel hub plugin (37:00) -> webinar
- BYOC tool in github


# Feedback:

utilize 10m resolution and split the polygon for smaller areas.

- splitting polygon, lets assume it is just rectangle or square... so I will try to split it into 4 boxes
- then I should probably ... so the approcach would be probably this - get polygon, dissect it, get data for each and then merge it... there should be some function rasterio.merge if I remember correctly - saw it somewhere pop out. but... do utm before or after...

ok to do that, I need to create test as I dont want to mingle with my existing code right now.

GPT told me that I should first convert the lon/lat into utm and do the splitting later because of geometry, otherwise pixel resolution will differ between tiles.

done tests and the tiles are splitted, checking by eye.

so now I need to do this: for each subtile i need data and then stich it. so lets get back into test.

I need token, but only once ofcourse...
oooh it is not trivial now.... i need acquisition dates, but that is only flyover on that area so... lets assume that the dates even on split area are ideal.

aaaah, now I got no data for one chunk from the bounding box :D

encountered these errors:
```
TIFFFetchDirectory: Sanity check failed
TIFFReadEncodedStrip() failed
```

ok after a bit of thinkering and chatting with copilot back and forth... I have and output... but! its all black!!! oh my!

so apparently, setting the -99999 for no data is not exactly good idea, but, I figured yout that I just might specify the null, or NaN value into "nodata" in meta.update... like this:

```python
out_meta.update({
    "height": mosaic.shape[1],
    "width": mosaic.shape[2],
    "transform": out_transform,
    "nodata": -99999.0
})
# and
mosaic = mosaic.astype("float32")
# mosaic[np.isnan(mosaic)] = -99999 # this is actually wrong, it should be:
mosaic[mosaic == -99999] = np.nan

```

let's try! eh, no, just in the sentinel data. I believe the data from clms are already in a good shape.

Ok, done, now I can sleep in peace :)

