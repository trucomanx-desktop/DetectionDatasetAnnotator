#!/usr/bin/python3

'''
## ubuntu ##
python3 -m venv venv-temporal
source venv-temporal/bin/activate
pip install --upgrade pip

## windows ##
python -m venv venv-temporal
venv-temporal\Scripts\activate
python -m pip install --upgrade pip

pip install pyinstaller pyinstaller-hooks-contrib
pip install -r requirements.txt
cd src

## ubuntu ##
python3 -m PyInstaller --onefile --windowed --name detection-dataset-labeler --add-data "detection_dataset_annotator/icons:icons" --collect-all PyQt5  program_launcher_labeler.py


## windows ##
python -m PyInstaller --onefile --windowed --name detection-dataset-labeler --add-data "detection_dataset_annotator/icons;icons" --collect-all PyQt5  program_launcher_labeler.py

'''

import os
from PyQt5.QtCore import QLibraryInfo

os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.location(
    QLibraryInfo.PluginsPath
)


from detection_dataset_annotator.program_labeler import main

if __name__ == "__main__":
    main()

