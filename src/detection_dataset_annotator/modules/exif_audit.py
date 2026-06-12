#!/usr/bin/python3

import os

from PIL import Image
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QProgressBar,
)


ORIENTATION_TAG = 274


class ExifAuditWindow(QDialog):

    def __init__(self, dataset_path, parent=None):
        super().__init__(parent)

        self.dataset_path = dataset_path
        self.images_path = os.path.join(dataset_path, "images")

        self.setWindowTitle("EXIF Orientation Audit")
        self.resize(900, 600)

        self.init_ui()

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------
    def init_ui(self):

        layout = QVBoxLayout(self)

        #
        # Dataset
        #
        self.lbl_dataset = QLabel(
            f"<b>Dataset:</b> {self.dataset_path}"
        )
        layout.addWidget(self.lbl_dataset)

        #
        # Summary
        #
        self.lbl_summary = QLabel(
            "Press Scan to analyze dataset."
        )
        layout.addWidget(self.lbl_summary)

        #
        # Table
        #
        self.table = QTableWidget(0, 3)

        self.table.setHorizontalHeaderLabels(
            [
                "Image",
                "Orientation",
                "Status"
            ]
        )

        self.table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.Stretch
        )

        self.table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeToContents
        )

        self.table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeToContents
        )

        layout.addWidget(self.table)

        #
        # Progress
        #
        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        #
        # Buttons
        #
        buttons = QHBoxLayout()

        self.btn_scan = QPushButton("Scan")
        self.btn_scan.clicked.connect(self.scan_images)

        self.btn_fix_selected = QPushButton("Fix Selected")
        self.btn_fix_selected.clicked.connect(
            self.fix_selected
        )

        self.btn_fix_all = QPushButton("Fix All")
        self.btn_fix_all.clicked.connect(
            self.fix_all
        )

        buttons.addWidget(self.btn_scan)
        buttons.addWidget(self.btn_fix_selected)
        buttons.addWidget(self.btn_fix_all)

        layout.addLayout(buttons)

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def get_orientation(self, image_path):

        try:
            img = Image.open(image_path)
            exif = img.getexif()

            if exif:
                return exif.get(
                    ORIENTATION_TAG,
                    1
                )

        except Exception:
            pass

        return 1

    def orientation_description(self, value):

        mapping = {
            1: "OK",
            2: "Mirror Horizontal",
            3: "Rotate 180",
            4: "Mirror Vertical",
            5: "Mirror + Rotate 90 CCW",
            6: "Rotate 90 CW",
            7: "Mirror + Rotate 90 CW",
            8: "Rotate 90 CCW",
        }

        return mapping.get(
            value,
            "Unknown"
        )

    def list_images(self):

        valid_ext = (
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".tif",
            ".tiff",
            ".webp",
        )

        images = []

        if not os.path.isdir(self.images_path):
            return images

        for name in os.listdir(self.images_path):

            if name.lower().endswith(valid_ext):
                images.append(
                    os.path.join(
                        self.images_path,
                        name
                    )
                )

        images.sort()

        return images

    # ---------------------------------------------------------
    # Scan
    # ---------------------------------------------------------
    def scan_images(self):

        self.table.setRowCount(0)

        images = self.list_images()

        total = len(images)
        pending = 0

        self.progress.setMaximum(total)

        for idx, image_path in enumerate(images):

            orientation = self.get_orientation(
                image_path
            )

            status = (
                "Needs Fix"
                if orientation != 1
                else "OK"
            )

            if orientation != 1:
                pending += 1

            row = self.table.rowCount()

            self.table.insertRow(row)

            self.table.setItem(
                row,
                0,
                QTableWidgetItem(
                    os.path.basename(image_path)
                )
            )

            self.table.setItem(
                row,
                1,
                QTableWidgetItem(
                    str(orientation)
                )
            )

            self.table.setItem(
                row,
                2,
                QTableWidgetItem(status)
            )

            self.progress.setValue(idx + 1)

        self.lbl_summary.setText(
            f"<b>Total:</b> {total} | "
            f"<b>Need Fix:</b> {pending} | "
            f"<b>OK:</b> {total - pending}"
        )

    # ---------------------------------------------------------
    # Fix image
    # ---------------------------------------------------------
    def fix_image(self, image_path):

        try:
            from PIL import ImageOps

            img = Image.open(image_path)

            img = ImageOps.exif_transpose(img)

            exif = img.getexif()

            exif[ORIENTATION_TAG] = 1

            img.save(
                image_path,
                exif=exif
            )

            return True

        except Exception as e:

            print(
                f"ERROR: {image_path}: {e}"
            )

            return False

    # ---------------------------------------------------------
    # Fix Selected
    # ---------------------------------------------------------
    def fix_selected(self):

        rows = sorted(
            {
                item.row()
                for item in self.table.selectedItems()
            }
        )

        if not rows:
            return

        fixed = 0

        for row in rows:

            filename = self.table.item(
                row,
                0
            ).text()

            image_path = os.path.join(
                self.images_path,
                filename
            )

            orientation = int(
                self.table.item(
                    row,
                    1
                ).text()
            )

            if orientation == 1:
                continue

            if self.fix_image(image_path):
                fixed += 1

        QMessageBox.information(
            self,
            "EXIF",
            f"{fixed} image(s) fixed."
        )

        self.scan_images()

    # ---------------------------------------------------------
    # Fix All
    # ---------------------------------------------------------
    def fix_all(self):

        reply = QMessageBox.question(
            self,
            "EXIF",
            (
                "This operation will modify "
                "the image files permanently.\n\n"
                "Continue?"
            )
        )

        if reply != QMessageBox.Yes:
            return

        fixed = 0

        images = self.list_images()

        self.progress.setMaximum(
            len(images)
        )

        for idx, image_path in enumerate(images):

            orientation = self.get_orientation(
                image_path
            )

            if orientation != 1:

                if self.fix_image(image_path):
                    fixed += 1

            self.progress.setValue(idx + 1)

        QMessageBox.information(
            self,
            "EXIF",
            f"{fixed} image(s) fixed."
        )

        self.scan_images()
        
if __name__ == "__main__":

    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    w = ExifAuditWindow(
        "/mnt/boveda/working/"
    )

    w.show()

    sys.exit(app.exec_())
