def test_environment():
    import cv2
    import numpy as np
    import PIL
    import pandas as pd
    import openpyxl
    import easyocr
    assert cv2.__version__ is not None
    assert np.__version__ is not None
    assert PIL.__version__ is not None
    assert pd.__version__ is not None
    assert openpyxl.__version__ is not None
    assert easyocr.__file__ is not None
