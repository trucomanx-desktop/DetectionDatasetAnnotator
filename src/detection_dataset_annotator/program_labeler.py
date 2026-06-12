#!/usr/bin/python3
"""
Simple JSON Annotator
- Seleciona pasta do dataset com subpasta images/
- Cria labels/ com arquivos .json por imagem
- Bounding boxes com label alfanumérico livre (sem classes fixas)
- Formato JSON salvo:
  {
    "image": "images/imagem.png",
    "objects": [
      {"label": "parafuso_m6", "bbox": [x1, y1, x2, y2]},
      ...
    ]
  }
"""

import os
import sys
import json
import signal
import subprocess

from PIL import Image

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGraphicsView,
    QGraphicsScene, QGraphicsRectItem, QGraphicsSimpleTextItem,
    QFileDialog, QLineEdit, QGroupBox, QScrollArea,
    QAbstractItemView, QSizePolicy, QMessageBox, QFrame,
    QProgressBar, QAction
)
from PyQt5.QtCore import Qt, QUrl, QRectF
from PyQt5.QtGui import (
    QDesktopServices, QIcon, QColor, QPen, QBrush, QFont, QPixmap, QPainter
)



import detection_dataset_annotator.about as about
import detection_dataset_annotator.modules.configure as configure

from detection_dataset_annotator.desktop import create_desktop_file
from detection_dataset_annotator.desktop import create_desktop_directory
from detection_dataset_annotator.desktop import create_desktop_menu

from detection_dataset_annotator.modules.wabout    import show_about_window
from detection_dataset_annotator.modules.resources import resource_path
from detection_dataset_annotator.modules.exif_audit import ExifAuditWindow

#-------------------------------------------------------------------------------

CONFIG_PATH = os.path.join( os.path.expanduser("~"),
                            ".config",
                            about.__package__,
                            about.__program_labeler__+".json")

DEFAULT_CONTENT={   
    "toolbar_exif": "EXIF",
    "toolbar_exif_tooltip": "Audit and fix image EXIF orientation",
    "toolbar_configure": "Configure",
    "toolbar_configure_tooltip": "Open the configure Json file",
    "toolbar_about": "About",
    "toolbar_about_tooltip": "About the program",
    "toolbar_coffee": "Coffee",
    "toolbar_coffee_tooltip": "Buy me a coffee (TrucomanX)",
    "window_width": 1200,
    "window_height": 800,
    "button_draw_box": "Draw Box",
    "button_draw_box_tooltip": "Press the button, then select the box in the image.",
    "group_bounding_boxes": "Bounding Boxes",
    "group_selected_box": "Label of the Selected Box",
    "label_select_box": "Select a box to edit your label.",
    "label_edit_placeholder": "ex: screw_m6",
    "label_edit_tooltip": "Here can be change the label of bounding box",
    "button_apply": "Apply Label (Enter)",
    "button_apply_tooltip": "Apply Label by pressing Enter",
    "button_save": "Save labels",
    "button_save_tooltip": "Save notes and generates JSON files.",
    "button_open_dataset": "Open Dataset",
    "button_open_dataset_tooltip": "Open the dataset directory",
    "label_no_dataset": "No dataset open",
    "label_images": "Images",
    "color_background_1": "#1e1e2e",
    "color_background_2": "#313244",
    "color_tooltip_text": "#cccccc",
    "msg_status_init": "Open a dataset to get started |  Delete = remove selected box",
    "msg_error": "Error",
    "msg_select_dataset_folder": "Select dataset folder",
    "boundingbox_unknown_label": "unknown",
    "boundingbox_fontsize": 32,
    "boundingbox_linewidth": 12,
    "boundingbox_color_dash": "#FFFFFF",
    "boundingbox_colors": [ "#E63946", "#2A9D8F", "#E9C46A", "#457B9D",
                            "#F4A261", "#6A4C93", "#52B788", "#FF6B6B",
                            "#4CC9F0", "#F77F00" ],
}

configure.verify_default_config(CONFIG_PATH,default_content=DEFAULT_CONTENT)
CONFIG=configure.load_config(CONFIG_PATH)

#-------------------------------------------------------------------------------

# ─────────────────────────────────────────
# Paleta de cores para distinguir boxes
# ─────────────────────────────────────────


def next_color(index):
    roulette = CONFIG["boundingbox_colors"]
    return QColor(roulette[index % len(roulette)])


# ─────────────────────────────────────────
# BoundingBox – item gráfico
# ─────────────────────────────────────────
class BoundingBox(QGraphicsRectItem):
    HANDLE = 16  # tamanho da alça de resize

    def __init__(self, rect, label, color, parent=None):
        super().__init__(rect, parent)
        self.label = label
        self.color = color
        self._resizing = False

        self.setFlags(
            QGraphicsRectItem.ItemIsSelectable |
            QGraphicsRectItem.ItemIsMovable |
            QGraphicsRectItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._apply_style()
        self._build_label()

    def _apply_style(self):
        self.setPen(QPen(self.color, CONFIG["boundingbox_linewidth"]))
        self.setBrush(QBrush(QColor(0, 0, 0, 0)))

    def _build_label(self):
        # Fundo do texto
        self._bg = QGraphicsRectItem(self)
        self._bg.setPen(QPen(Qt.NoPen))
        self._bg.setBrush(QBrush(QColor(0, 0, 0, 160)))

        # Texto
        self._text = QGraphicsSimpleTextItem(self.label, self)
        self._text.setBrush(QBrush(Qt.white))
        font = QFont("Monospace")
        font.setPointSize(CONFIG["boundingbox_fontsize"])
        font.setBold(True)
        self._text.setFont(font)

        self._reposition_label()

    def _reposition_label(self):
        r = self.rect()
        tr = self._text.boundingRect()
        tx = r.x() + 3
        ty = r.y() + 3
        self._text.setPos(tx, ty)
        self._bg.setRect(r.x(), r.y(), tr.width() + 6, tr.height() + 4)

    def update_label(self, new_label):
        self.label = new_label
        self._text.setText(new_label)
        self._reposition_label()

    def update_color(self, color):
        self.color = color
        self._apply_style()

    # ── hover / resize ──
    def _in_handle(self, pos):
        r = self.rect()
        return QRectF(r.right() - self.HANDLE, r.bottom() - self.HANDLE,
                      self.HANDLE * 2, self.HANDLE * 2).contains(pos)

    def hoverMoveEvent(self, ev):
        self.setCursor(Qt.SizeFDiagCursor if self._in_handle(ev.pos())
                       else Qt.ArrowCursor)
        super().hoverMoveEvent(ev)

    def mousePressEvent(self, ev):
        if self._in_handle(ev.pos()):
            self._resizing = True
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._resizing:
            r = self.rect()
            r.setBottomRight(ev.pos())
            self.setRect(r)
            self._reposition_label()
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._resizing = False
        super().mouseReleaseEvent(ev)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemSelectedChange:
            pen = QPen(Qt.white if value else self.color, CONFIG["boundingbox_linewidth"])
            self.setPen(pen)
        return super().itemChange(change, value)


# ─────────────────────────────────────────
# Cena de anotação
# ─────────────────────────────────────────
class AnnotateScene(QGraphicsScene):
    def __init__(self, on_selection_change, parent=None):
        super().__init__(parent)
        self.on_selection_change = on_selection_change
        self.box_items = []
        self._drawing = False
        self._start = None
        self._temp = None
        self._color_index = 0

    def start_draw_mode(self):
        self._drawing = True

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Delete:
            for item in list(self.selectedItems()):
                if isinstance(item, BoundingBox):
                    self.removeItem(item)
                    self.box_items.remove(item)
            self.on_selection_change([])
        else:
            super().keyPressEvent(ev)

    def mousePressEvent(self, ev):
        if self._drawing and ev.button() == Qt.LeftButton:
            self._start = ev.scenePos()
            self._temp = QGraphicsRectItem(QRectF(self._start, self._start))
            dash_pen = QPen( QColor(CONFIG["boundingbox_color_dash"]), 
                             CONFIG["boundingbox_linewidth"], 
                             Qt.DashLine )
            self._temp.setPen(dash_pen)
            self.addItem(self._temp)
        else:
            super().mousePressEvent(ev)
            sel = [i for i in self.selectedItems() if isinstance(i, BoundingBox)]
            self.on_selection_change(sel)

    def mouseMoveEvent(self, ev):
        if self._temp:
            self._temp.setRect(QRectF(self._start, ev.scenePos()).normalized())
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._temp:
            rect = self._temp.rect()
            self.removeItem(self._temp)
            self._temp = None
            self._drawing = False
            if rect.width() > 4 and rect.height() > 4:
                color = next_color(self._color_index)
                self._color_index += 1
                box = BoundingBox(rect, CONFIG["boundingbox_unknown_label"], color)
                self.addItem(box)
                self.box_items.append(box)
                # seleciona automaticamente para editar
                self.clearSelection()
                box.setSelected(True)
                self.on_selection_change([box])
        else:
            super().mouseReleaseEvent(ev)


# ─────────────────────────────────────────
# Painel de edição de boxes (direita)
# ─────────────────────────────────────────
class BoxEditorPanel(QWidget):
    """Mostra a lista de boxes da imagem atual e permite editar labels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = None
        self._boxes = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        self.color_background_1 = CONFIG["color_background_1"]
        self.color_background_2 = CONFIG["color_background_2"]

        # ── Botão "Desenhar Box" ──
        self.btn_draw = QPushButton(CONFIG["button_draw_box"])
        self.btn_draw.setToolTip(CONFIG["button_draw_box_tooltip"])
        self.btn_draw.setIcon(QIcon(resource_path('icons', 'button_add_green.png'))) 
        self.btn_draw.setEnabled(False)
        self.btn_draw.setStyleSheet("""
            QPushButton {
                background: #2A9D8F; color: white;
                border: none; border-radius: 4px;
                padding: 8px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #21867a; }
            QPushButton:disabled { background: #555; color: #999; }
        """)
        self.btn_draw.clicked.connect(self._on_draw)
        layout.addWidget(self.btn_draw)

        # ── Lista de boxes ──
        grp = QGroupBox(CONFIG["group_bounding_boxes"])
        grp.setStyleSheet("QGroupBox { color: #ccc; font-weight: bold; }")
        grp_layout = QVBoxLayout(grp)

        self.list_boxes = QListWidget()
        self.list_boxes.setStyleSheet(f"""
            QListWidget {{
                background: {self.color_background_1}; color: #cdd6f4;
                border: 1px solid #444; border-radius: 4px;
            }}
            QListWidget::item:selected {{ background: {self.color_background_2}; }}
        """)
        self.list_boxes.itemClicked.connect(self._on_list_click)
        grp_layout.addWidget(self.list_boxes)
        layout.addWidget(grp)

        # ── Editor de label ──
        grp2 = QGroupBox(CONFIG["group_selected_box"])
        grp2.setStyleSheet("QGroupBox { color: #ccc; font-weight: bold; }")
        grp2_layout = QVBoxLayout(grp2)

        self.lbl_hint = QLabel(CONFIG["label_select_box"])
        self.lbl_hint.setStyleSheet("color: #888; font-size: 11px;")
        self.lbl_hint.setWordWrap(True)
        grp2_layout.addWidget(self.lbl_hint)

        self.edit_label = QLineEdit()
        self.edit_label.setPlaceholderText(CONFIG["label_edit_placeholder"])
        self.edit_label.setToolTip(CONFIG["label_edit_tooltip"])
        self.edit_label.setEnabled(False)
        self.edit_label.setStyleSheet(f"""
            QLineEdit {{
                background: {self.color_background_1}; color: #cdd6f4;
                border: 1px solid #6c7086; border-radius: 4px;
                padding: 6px; font-size: 14px;
            }}
            QLineEdit:focus {{ border-color: #89b4fa; }}
            QLineEdit:disabled {{ background: #181825; color: #555; }}
        """)
        self.edit_label.returnPressed.connect(self._apply_label)
        grp2_layout.addWidget(self.edit_label)

        self.btn_apply = QPushButton(CONFIG["button_apply"])
        self.btn_apply.setIcon(QIcon(resource_path('icons', 'go-down.png'))) 
        self.btn_apply.setToolTip(CONFIG["button_apply_tooltip"])
        self.btn_apply.setEnabled(False)
        self.btn_apply.setStyleSheet(f"""
            QPushButton {{
                background: #89b4fa; color: {self.color_background_1};
                border: none; border-radius: 4px;
                padding: 6px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #74c7ec; }}
            QPushButton:disabled {{ background: {self.color_background_2}; color: #555; }}
        """)
        self.btn_apply.clicked.connect(self._apply_label)
        grp2_layout.addWidget(self.btn_apply)

        layout.addWidget(grp2)


        # ── Botão Salvar ──
        self.btn_save = QPushButton(CONFIG["button_save"])
        self.btn_save.setIcon(QIcon(resource_path('icons', 'media-floppy.png'))) 
        self.btn_save.setToolTip(CONFIG["button_save_tooltip"])
        self.btn_save.setEnabled(False)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background: #a6e3a1; color: {self.color_background_1};
                border: none; border-radius: 4px;
                padding: 8px; font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background: #94e2d5; }}
            QPushButton:disabled {{ background: {self.color_background_2}; color: #555; }}
        """)
        layout.addWidget(self.btn_save)

        layout.addStretch()

        self._selected_box = None

    def set_scene(self, scene):
        self._scene = scene

    def set_save_callback(self, fn):
        self.btn_save.clicked.connect(fn)

    def enable_draw(self, yes=True):
        self.btn_draw.setEnabled(yes)
        self.btn_save.setEnabled(yes)

    def _on_draw(self):
        if self._scene:
            self._scene.start_draw_mode()

    def refresh_list(self, boxes=None):
        """Atualiza a lista lateral com os boxes da cena."""
        if boxes is None and self._scene:
            boxes = self._scene.box_items
        self._boxes = boxes or []
        self.list_boxes.clear()
        for i, box in enumerate(self._boxes):
            item = QListWidgetItem(f"  [{i+1}]  {box.label}")
            item.setData(Qt.UserRole, i)
            self.list_boxes.addItem(item)

    def on_scene_selection(self, selected_boxes):
        """Chamado pela cena quando a seleção muda."""
        self.refresh_list()
        if selected_boxes:
            box = selected_boxes[0]
            self._selected_box = box
            self.edit_label.setEnabled(True)
            self.btn_apply.setEnabled(True)
            self.edit_label.setText(box.label)
            self.edit_label.setFocus()
            self.edit_label.selectAll()
            # realça na lista
            for i in range(self.list_boxes.count()):
                li = self.list_boxes.item(i)
                if self._boxes[li.data(Qt.UserRole)] is box:
                    self.list_boxes.setCurrentItem(li)
                    break
        else:
            self._selected_box = None
            self.edit_label.setEnabled(False)
            self.btn_apply.setEnabled(False)
            self.edit_label.clear()

    def _on_list_click(self, item):
        idx = item.data(Qt.UserRole)
        if self._scene and 0 <= idx < len(self._boxes):
            self._scene.clearSelection()
            self._boxes[idx].setSelected(True)
            self.on_scene_selection([self._boxes[idx]])

    def _apply_label(self):
        if self._selected_box:
            text = self.edit_label.text().strip()
            if text:
                self._selected_box.update_label(text)
                self.refresh_list()


# ─────────────────────────────────────────
# Janela principal
# ─────────────────────────────────────────
class SimpleAnnotatorApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(about.__program_labeler__)
        self.resize(CONFIG["window_width"], CONFIG["window_height"])
        self.setStyleSheet("QMainWindow { background: #181825; }")

        ## Icon
        # Get base directory for icons
        self.icon_path = resource_path('icons', 'labeler.svg')
        self.setWindowIcon(QIcon(self.icon_path)) 

        self.color_background_1 = CONFIG["color_background_1"]
        self.color_background_2 = CONFIG["color_background_2"]

        self.dataset_path = ""
        self.current_image = ""
        self.pixmap_item = None
        self._images = []

        self.create_toolbar()
        self._build_ui()

    def create_toolbar(self):
        # Toolbar exemplo (você pode adicionar actions depois)
        self.toolbar = self.addToolBar("Main Toolbar")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        
        #
        self.exif_action = QAction( QIcon(resource_path('icons', 'image.png')),
                                    CONFIG["toolbar_exif"],
                                    self )
        self.exif_action.setToolTip(CONFIG["toolbar_exif_tooltip"])
        self.exif_action.triggered.connect(self.open_exif_window)
        self.exif_action.setEnabled(False)
        self.toolbar.addAction(self.exif_action)

        
        # Adicionar o espaçador
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar.addWidget(spacer)
        
        #
        self.configure_action = QAction(QIcon(resource_path('icons', 'text-configure.png')), 
                                        CONFIG["toolbar_configure"], 
                                        self)
        self.configure_action.setToolTip(CONFIG["toolbar_configure_tooltip"])
        self.configure_action.triggered.connect(self.open_configure_editor)
        self.toolbar.addAction(self.configure_action)
        
        #
        self.about_action = QAction(QIcon(resource_path('icons', 'status_help.png')), 
                                    CONFIG["toolbar_about"], 
                                    self)
        self.about_action.setToolTip(CONFIG["toolbar_about_tooltip"])
        self.about_action.triggered.connect(self.open_about)
        self.toolbar.addAction(self.about_action)
        
        # Coffee
        self.coffee_action = QAction(   QIcon(resource_path('icons', 'emote-love.png')), 
                                        CONFIG["toolbar_coffee"], 
                                        self)
        self.coffee_action.setToolTip(CONFIG["toolbar_coffee_tooltip"])
        self.coffee_action.triggered.connect(self.on_coffee_action_click)
        self.toolbar.addAction(self.coffee_action)

    def open_exif_window(self):

        if not self.dataset_path:
            QMessageBox.warning(
                self,
                CONFIG["msg_error"],
                CONFIG["msg_select_dataset_folder"]
            )
            return

        dialog = ExifAuditWindow(
            dataset_path=self.dataset_path,
            parent=self
        )

        dialog.exec_()

    def open_configure_editor(self):
        if os.name == 'nt':  # Windows
            os.startfile(CONFIG_PATH)
        elif os.name == 'posix':  # Linux/macOS
            subprocess.run(['xdg-open', CONFIG_PATH])

    def on_coffee_action_click(self):
        QDesktopServices.openUrl(QUrl("https://ko-fi.com/trucomanx"))
    
    def open_about(self):
        data={
            "version": about.__version__,
            "package": about.__package__,
            "program_name": about.__program_labeler__,
            "author": about.__author__,
            "email": about.__email__,
            "description": about.__description__,
            "url_source": about.__url_source__,
            "url_doc": about.__url_doc__,
            "url_funding": about.__url_funding__,
            "url_bugs": about.__url_bugs__
        }
        show_about_window(data,self.icon_path)
        

    # ── Construção da UI ──────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {self.color_background_2}; }}")

        # ── Painel esquerdo: lista de imagens ──
        left = QWidget()
        left.setStyleSheet(f"background: {self.color_background_1};")
        left.setMinimumWidth(200)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)


        self.btn_open = QPushButton(CONFIG["button_open_dataset"])
        self.btn_open.setToolTip(CONFIG["button_open_dataset_tooltip"])
        self.btn_open.setIcon(QIcon(resource_path('icons', 'folder-drag-accept.png'))) 
        self.btn_open.setStyleSheet(f"""
            QPushButton {{
                background: #cba6f7; color: {self.color_background_1};
                border: none; border-radius: 4px;
                padding: 8px; font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background: #b4befe; }}
        """)
        self.btn_open.clicked.connect(self._select_dataset)
        left_layout.addWidget(self.btn_open)


        self.lbl_path = QLabel(CONFIG["label_no_dataset"])
        self.lbl_path.setStyleSheet("color: #6c7086; font-size: 10px;")
        self.lbl_path.setWordWrap(True)
        left_layout.addWidget(self.lbl_path)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("%v / %m noted")
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background: {self.color_background_2}; border-radius: 4px;
                color: #cdd6f4; font-size: 10px; height: 14px;
            }}
            QProgressBar::chunk {{ background: #a6e3a1; border-radius: 4px; }}
        """)
        self.progress.setValue(0)
        self.progress.setMaximum(1)
        left_layout.addWidget(self.progress)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {self.color_background_2};")
        left_layout.addWidget(sep)


        lbl_imgs = QLabel(CONFIG["label_images"])
        lbl_imgs.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: bold;")
        left_layout.addWidget(lbl_imgs)

        self.list_images = QListWidget()
        self.list_images.setStyleSheet(f"""
            QListWidget {{
                background: #181825; color: #cdd6f4;
                border: 1px solid {self.color_background_2}; border-radius: 4px;
                font-size: 12px;
            }}
            QListWidget::item {{ padding: 4px 6px; }}
            QListWidget::item:selected {{ background: #45475a; }}
            QListWidget::item:hover {{ background: {self.color_background_2}; }}
        """)
        self.list_images.currentItemChanged.connect(self._on_image_selected)
        left_layout.addWidget(self.list_images)

        splitter.addWidget(left)

        # ── Painel central: visualizador ──
        center = QWidget()
        center.setStyleSheet("background: #181825;")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(4, 4, 4, 4)
        center_layout.setSpacing(4)

        self.lbl_image_name = QLabel("—")
        self.lbl_image_name.setAlignment(Qt.AlignCenter)
        self.lbl_image_name.setStyleSheet("color: #a6adc8; font-size: 11px;")
        center_layout.addWidget(self.lbl_image_name)
        
        self.lbl_exif_warning = QLabel("")
        self.lbl_exif_warning.setAlignment(Qt.AlignCenter)
        font = self.lbl_exif_warning.font()
        font.setBold(True)
        self.lbl_exif_warning.setFont(font)
        center_layout.addWidget(self.lbl_exif_warning)

        self.scene = AnnotateScene(on_selection_change=self._on_box_selection)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setStyleSheet("background: #11111b; border: none;")
        self.view.setDragMode(QGraphicsView.NoDrag)
        center_layout.addWidget(self.view)

        splitter.addWidget(center)

        # ── Painel direito: editor ──
        self.editor = BoxEditorPanel()
        self.editor.setStyleSheet(f"background: {self.color_background_1};")
        self.editor.setFixedWidth(270)
        self.editor.set_scene(self.scene)
        self.editor.set_save_callback(self._save_annotations)
        splitter.addWidget(self.editor)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([210, 820, 270])

        root.addWidget(splitter)


        # Status bar
        self.statusBar().setStyleSheet("background: #181825; color: #6c7086; font-size: 11px;")
        self.statusBar().showMessage(CONFIG["msg_status_init"])

    # ── Seleção do dataset ────────────────
    def update_exif_warning(self, img_path):
        
        try:
            img = Image.open(img_path)
            orientation = img.getexif().get(274, 1)

            if orientation != 1:
                self.lbl_exif_warning.setText(
                    f"⚠ WARNING: EXIF Orientation={orientation}. "
                    "Normalize this image before annotation."
                )

                self.lbl_exif_warning.setStyleSheet("color: red;")
            else:
                self.lbl_exif_warning.setText("")
                self.lbl_exif_warning.setStyleSheet("")

        except Exception:
            self.lbl_exif_warning.setText("")
            self.lbl_exif_warning.setStyleSheet("")
        
    def _select_dataset(self):
        folder = QFileDialog.getExistingDirectory(self, "Select dataset folder")
        if not folder:
            return
        images_dir = os.path.join(folder, "images")
        if not os.path.isdir(images_dir):
            QMessageBox.warning(self, "Invalid directory",
                                f"I didn't find the 'images' subfolder in:\n{folder}")
            return
        self.dataset_path = folder
        self.lbl_path.setText(folder)

        exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        self._images = sorted(
            f for f in os.listdir(images_dir)
            if os.path.splitext(f)[1].lower() in exts
        )

        self.list_images.clear()
        for img in self._images:
            item = QListWidgetItem(img)
            # marca se já tem JSON salvo
            json_path = self._json_path_for(img)
            if os.path.exists(json_path):
                item.setForeground(QColor("#a6e3a1"))
            self.list_images.addItem(item)

        self._update_progress()
        self.editor.enable_draw(True)
        self.statusBar().showMessage(f"{len(self._images)} images uploaded from: {folder}")
        
        self.exif_action.setEnabled(True)

    def _json_path_for(self, img_name):
        base, _ = os.path.splitext(img_name)
        return os.path.join(self.dataset_path, "labels", base + ".json")

    def _update_progress(self):
        total = len(self._images)
        done = sum(
            1 for img in self._images
            if os.path.exists(self._json_path_for(img))
        )
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)

    # ── Seleção de imagem ─────────────────
    def _on_image_selected(self, current, previous):
        if not current:
            return
        img_name = current.text()
        self.current_image = img_name
        self.lbl_image_name.setText(img_name)
        self._load_image(img_name)

    def _load_image(self, img_name):
        self.scene.clear()
        self.scene.box_items = []
        self.scene._color_index = 0
        self.editor.refresh_list([])
        self.editor.on_scene_selection([])

        img_path = os.path.join(self.dataset_path, "images", img_name)
        
        self.update_exif_warning(img_path)
        
        pixmap = QPixmap(img_path)
        if pixmap.isNull():
            self.statusBar().showMessage(f"Error loading: {img_path}")
            return
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

        # Carrega anotações existentes
        json_path = self._json_path_for(img_name)
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            w = pixmap.width()
            h = pixmap.height()
            for obj in data.get("objects", []):
                label = obj.get("label", CONFIG["boundingbox_unknown_label"])
                b = obj.get("bbox", [0.0, 0.0, 1.0, 1.0])
                x1, y1, x2, y2 = b
                rect = QRectF(x1 * w, y1 * h, (x2 - x1) * w, (y2 - y1) * h)
                color = next_color(self.scene._color_index)
                self.scene._color_index += 1
                box = BoundingBox(rect, label, color)
                self.scene.addItem(box)
                self.scene.box_items.append(box)
            self.editor.refresh_list(self.scene.box_items)
            self.statusBar().showMessage(
                f"{img_name}  — {len(self.scene.box_items)} box(es) carregados"
            )
        else:
            self.statusBar().showMessage(f"{img_name}  — sem anotações ainda")

    # ── Callbacks de seleção ──────────────
    def _on_box_selection(self, selected_boxes):
        self.editor.on_scene_selection(selected_boxes)

    # ── Salvar ────────────────────────────
    def _save_annotations(self):
        if not self.current_image or not self.dataset_path:
            return
        if not self.pixmap_item:
            return

        labels_dir = os.path.join(self.dataset_path, "labels")
        os.makedirs(labels_dir, exist_ok=True)

        w = self.pixmap_item.pixmap().width()
        h = self.pixmap_item.pixmap().height()
        objects = []
        for box in self.scene.box_items:
            r = box.sceneBoundingRect()
            x1 = round(r.x() / w, 6)
            y1 = round(r.y() / h, 6)
            x2 = round((r.x() + r.width()) / w, 6)
            y2 = round((r.y() + r.height()) / h, 6)
            objects.append({
                "label": box.label,
                "bbox": [x1, y1, x2, y2]
            })

        rel_img = "images/" + self.current_image
        data = {
            "image": rel_img,
            "objects": objects
        }

        json_path = self._json_path_for(self.current_image)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Atualiza cor do item na lista (verde = anotado)
        for i in range(self.list_images.count()):
            item = self.list_images.item(i)
            if item.text() == self.current_image:
                item.setForeground(QColor("#a6e3a1"))
                break

        self._update_progress()
        self.statusBar().showMessage(
            f"Saved: {json_path}  ({len(objects)} objet(s))"
        )


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────
def main():

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    create_desktop_directory()    
    create_desktop_menu()
    create_desktop_file(os.path.join("~",".local","share","applications"), 
                        program_name = about.__program_labeler__)
    
    for n in range(len(sys.argv)):
        if sys.argv[n] == "--autostart":
            create_desktop_directory(overwrite = True)
            create_desktop_menu(overwrite = True)
            create_desktop_file(os.path.join("~",".config","autostart"), 
                                overwrite=True, 
                                program_name = about.__program_labeler__)
            return
        if sys.argv[n] == "--applications":
            create_desktop_directory(overwrite = True)
            create_desktop_menu(overwrite = True)
            create_desktop_file(os.path.join("~",".local","share","applications"), 
                                overwrite=True, 
                                program_name = about.__program_labeler__)
            return

    app = QApplication(sys.argv)
    app.setApplicationName(about.__program_labeler__) 
    app.setStyle("Fusion")

    # Tooltip legível: fundo branco, texto preto
    color_tooltip_text = CONFIG["color_tooltip_text"]
    app.setStyleSheet(f"""
        QToolTip {{
            color: {color_tooltip_text};
            border: 1px solid #6c7086;
            padding: 4px;
            font-size: 18px;
        }}
    """)

    window = SimpleAnnotatorApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
