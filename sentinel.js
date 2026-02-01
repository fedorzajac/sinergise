//VERSION=3
    function setup() {
    return {
        input: ["B04", "B08", "SCL"],
        output: { bands: 1, sampleType: "FLOAT32" },
    }
    }

    // SCL classes considered "bad"
    var BAD_SCL = [
        1, // Saturated / defective
        3, // Cloud shadow
        8, // Cloud medium probability
        9, // Cloud high probability
        10, // Thin cirrus
        11 // Snow / ice
    ];

    function evaluatePixel(s) {
    // If pixel is bad → return nodata
        if (BAD_SCL.includes(s.SCL)) {
            return [NaN];
        }
        // Else compute NDVI
        var ndvi = (s.B08 - s.B04) / (s.B08 + s.B04); // no need to add 0.000001
        return [ndvi];
    }
