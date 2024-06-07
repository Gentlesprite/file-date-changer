# coding=UTF-8
# Author:Gentlesprite
# Software:PyCharm
# Time:2024/4/7 19:24
# File:app
import os
import sys
from datetime import datetime
from enum import Enum
from typing import Optional

from PySide6.QtCore import Qt, QLocale, QTranslator, QDateTime, QDate, QTime, Signal, QSettings, QSize, QEventLoop, \
    QTimer
from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtWidgets import QApplication, QFileDialog, QTableWidgetItem, QDialog, QHeaderView, QWidget, QFrame, \
    QHBoxLayout
from loguru import logger
from qfluentwidgets import setThemeColor, setTheme, Theme, RoundMenu, Action, MessageBox, TableItemDelegate, \
    NavigationItemPosition, FluentWindow, SubtitleLabel, setFont, toggleTheme, SplashScreen, theme
from qfluentwidgets.common import FluentIcon as FIF
from win32file import CreateFile, SetFileTime, CloseHandle
from win32file import GENERIC_READ, GENERIC_WRITE, OPEN_EXISTING
from ui import Ui_Form
from ui_sec_menu import Ui_Dialog
import res_rc
import win32timezone


class UserFormChangeMode(Enum):
    new = 0
    path = 1
    single_local_time = 2
    multiple_local_time = 3
    global_time = 4


class MouseEvent(Enum):
    left_button = 0
    right_button = 1

    def _text(self):
        return {
            MouseEvent.left_button: '[鼠标左键]',
            MouseEvent.right_button: '[鼠标右键]'
        }[self]

    @staticmethod
    def _status(index):
        return ['[单击]', '[双击]'][index]

    @property
    def single_click(self):
        return self._text() + MouseEvent._status(0)

    @property
    def double_click(self):
        return self._text() + MouseEvent._status(1)


class StatusInfo(Enum):
    current = 0
    actual = 1
    change = 2
    setting = 3

    def text(self):
        return {
            StatusInfo.current: '当前',
            StatusInfo.actual: '实际',
            StatusInfo.change: '变更',
            StatusInfo.setting: '设置'
        }[self]


class TableRange(Enum):
    path = 0
    create_time = 1
    modify_time = 2
    access_time = 3
    file_name = 4

    def only_text(self):
        return {
            TableRange.path: '路径',
            TableRange.create_time: '创建时间',
            TableRange.modify_time: '修改时间',
            TableRange.access_time: '访问时间',
            TableRange.file_name: '文件名',
        }[self]

    def status_text(self, status: StatusInfo):
        return status.text() + self.only_text()

    @staticmethod
    def get_text(value: int):
        for member in TableRange:
            if member.value == value:
                return member.only_text()


class InterFace(QWidget, Ui_Form):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)


class Widget(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.label = SubtitleLabel(text, self)
        self.hBoxLayout = QHBoxLayout(self)
        setFont(self.label, 24)
        self.label.setAlignment(Qt.AlignCenter)
        self.hBoxLayout.addWidget(self.label, 1, Qt.AlignCenter)
        # 必须给子界面设置全局唯一的对象名
        self.setObjectName(text.replace(' ', '-'))


class SecDialog(QDialog, Ui_Dialog):  # 二级菜单窗口
    signal_time_data = Signal(str, tuple, dict or None)

    def __init__(self, logo):
        super(SecDialog, self).__init__()
        self.sd = Ui_Dialog()
        self.sd.setupUi(self)

        self.setWindowTitle('设置时间')
        self.setWindowIcon(logo)
        self.selected_items: dict = {}
        self.position: tuple = ()
        self.init_sec_time()
        self.sec_band()

    def sec_band(self):
        self.sd.push_button_ok.clicked.connect(self.close)

    def init_sec_time(self):
        self.sd.calendar_picker_ymd.setDate(QDateTime.currentDateTime().date())
        self.sd.time_picker_hms.setTime(QDateTime.currentDateTime().time())

    def init_sec_table(self, row: int, column: int):
        self.sd.table_widget_sec_info_bar.setRowCount(row)
        self.sd.table_widget_sec_info_bar.setColumnCount(column)
        self.sd.table_widget_sec_info_bar.setVerticalHeaderLabels(
            [TableRange.file_name.status_text(StatusInfo.current)])
        self.sd.table_widget_sec_info_bar.setHorizontalHeaderLabels(['更多详细信息'])
        self.sd.table_widget_sec_info_bar.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sd.table_widget_sec_info_bar.setItemDelegate(
            CustomDelegate(self.sd.table_widget_sec_info_bar))

    def ymd_hms(self) -> str:
        ymd = self.sd.calendar_picker_ymd.getDate()
        hms = self.sd.time_picker_hms.getTime()
        # 构造日期时间字符串
        return f"{ymd.year()}年{ymd.month()}月{ymd.day()}日 {hms.hour():02}:{hms.minute():02}:{hms.second():02}"

    def close(self):
        emit_time: str = self.ymd_hms()
        selected_items: dict = self.selected_items
        if self.signal_time_data.emit(emit_time, self.position, selected_items):  # 确保正常发送了时间信息再关闭窗口
            super().close()

    def set_selected_items(self, item: dict):
        self.selected_items = item

    def set_position(self, pos):
        self.position = pos


class CustomDelegate(TableItemDelegate):
    left_double_click_signal_pos_data = Signal(tuple)

    def createEditor(self, parent, option, index):
        pos: tuple = (index.row(), index.column())
        self.left_double_click_signal_pos_data.emit(pos)  # 发送双击位置


class APP(FluentWindow):
    build_time = '202404211901'
    software_name = 'FileDateChanger'
    software_name_version = '0.7.0'
    build_version = software_name_version.replace('.', '') + build_time
    software_name_author = 'Gentlesprite'
    copy_right = f'Copyright © 2024 {software_name_author}.'
    software_name_simplified_chinese = '文件日期修改器'
    software_name_author_simplified_chinese = '雪碧'
    software_info = '\n'.join(
        [f'软件版本 : version.{software_name_version}.build.{build_version}',
         f'软件名称 : {software_name_simplified_chinese}({software_name})',
         '语言 : 中文简体(Simplified Chinese)',
         f'软件作者 : {software_name_author_simplified_chinese}({software_name_author})',
         '操作系统 : Winodws',
         '构建 : AMD64', copy_right])
    software_logo = ':/logo0.4.ico'
    software_theme_color = '#28afe9'
    software_theme_mode = Theme.AUTO
    default_path = os.path.abspath(os.getcwd())
    work_dir = os.path.join(os.path.join(os.getenv('APPDATA'), software_name))
    setting_path = os.path.join(work_dir, 'config.ini')
    log_path = os.path.join(work_dir,
                            software_name + '_' + software_name_version.replace('.', '_') + '.log')  # 日志路径

    def __init__(self):
        super(APP, self).__init__()
        self.file_name: list = []  # 存储路径->[路径]
        self.file_info: dict = {}  # 存储->{路径:[创建时间,修改时间,访问时间]}
        self.current_left_click_row: int = 0  # 初始化当前鼠标左键单击的行
        self.current_left_click_column: int = 0  # 初始化当前鼠标左键单击的列
        self.current_right_click_row: int = 0  # 初始化当前鼠标右键单击的行
        self.current_right_click_column: int = 0  # 初始化当前鼠标右键单击的列
        self.current_left_double_click_row: int = 0  # 初始化当前鼠标左键双击的列
        self.current_left_double_click_column: int = 0  # 初始化当前鼠标左键双击的列
        self.open_dir_path: str = APP.default_path  # 初始化选择文件夹打开的路径
        self.ui = InterFace(self)
        self.addSubInterface(interface=self.ui,
                             icon=FIF.HOME,
                             position=NavigationItemPosition.TOP,
                             text='主页',
                             isTransparent=True)
        self.addSubInterface(interface=Widget(APP.software_info, self),
                             icon=FIF.INFO,
                             position=NavigationItemPosition.TOP,
                             text='信息',
                             isTransparent=True)
        self.setting = QSettings(APP.setting_path, QSettings.Format.IniFormat, self)
        self.init_setting()  # 初始化配置
        self.init_ui()  # 初始化主题
        self.tool_tips()  # 设置控件提示
        self.ui.tool_button_open_dir.setIcon(FIF.FOLDER_ADD)  # 设置打开文件夹的按钮图标
        self.ui.tool_button_toggle_theme.setIcon(FIF.CONSTRACT)
        self.delegate: CustomDelegate = ...  # 定义表格自定义委托
        self.dialog = SecDialog(QIcon(APP.software_logo))  # 用户变更时间的二级窗口
        self.local_change_flag = False
        self.global_change_flag = False
        self.local_change_create_time_flag = False
        self.init_table()  # 初始化表格内容
        self.band()  # 初始化绑定按键

    def tool_tips(self):
        self.ui.text_edit_path_input.setToolTip(
            '将文件拖入、粘贴到此处以开始,或点击右边添加文件图标,也可复制或手动输入文件路径到此处以回车换行作为分割符以多个文件,表格中成功显示视为有效文件。')
        self.ui.text_edit_path_input.setPlaceholderText(
            '将文件拖入、粘贴到此处以开始,或点击右边添加文件图标,也可复制或手动输入文件路径到此处以回车换行作为分割符以多个文件,表格中成功显示视为有效文件。')
        self.ui.calendar_picker_ymd.setToolTip('选择一个年月日作为全局的设定。')
        self.ui.time_picker_hms.setToolTip('选择一个时分秒作为全局的设定。')
        self.ui.push_button_change_time.setToolTip('点此进行提交修改。')
        self.ui.tool_button_open_dir.setToolTip('在弹出的对话框选择打开一个或多个文件。')
        self.ui.check_box_create_time.setToolTip('控制全局是否对创建时间进行修改的开关。')
        self.ui.check_box_modify_time.setToolTip('控制全局是否对修改时间进行修改的开关。')
        self.ui.check_box_modify_time.setToolTip('控制全局是否对访问时间进行修改的开关')
        self.ui.tool_button_toggle_theme.setToolTip('在亮/暗色主题间切换,默认主题跟随系统。')
        self.ui.table_widget_info_bar.setToolTip('显示填入输入框中文件信息的表格。')

    def init_setting(self):
        try:
            self.ui.check_box_create_time.setChecked(bool(int(self.setting.value('CHECK/create_time'))))
            self.ui.check_box_modify_time.setChecked(bool(int(self.setting.value('CHECK/modify_time'))))
            self.ui.check_box_access_time.setChecked(bool(int(self.setting.value('CHECK/access_time'))))
            self.ui.check_box_auto_clear.setChecked(bool(int(self.setting.value('CHECK/auto_clear'))))
            last_open_dir: str = os.path.normpath(str(self.setting.value('PATH/last_open_dir')))
            self.open_dir_path: str = last_open_dir if os.path.isdir(last_open_dir) else self.open_dir_path
            theme_mode = self.setting.value('THEME/mode')
            if not theme_mode:
                setTheme(Theme.AUTO)
            elif theme_mode == Theme.LIGHT.value:
                setTheme(Theme.LIGHT)
            elif theme_mode == Theme.DARK.value:
                setTheme(Theme.DARK)

        except Exception as error:
            setTheme(Theme.AUTO)
            file_not_found = False
            try:
                os.remove(APP.setting_path)
            except Exception as e:
                file_not_found = True
                logger.error(e)
            finally:
                logger.info(
                    '已经删除错误的配置文件,在软件关闭后根据当前配置重新生成新的配置文件,此次运行配置参数将全部为默认。')
            if file_not_found:
                logger.warning('未找到配置文件!')
            else:
                logger.error(f'或配置文件出错:{error}')

    def closeEvent(self, event):
        self.setting.setValue('CHECK/create_time', int(self.ui.check_box_create_time.isChecked()))
        self.setting.setValue('CHECK/modify_time', int(self.ui.check_box_modify_time.isChecked()))
        self.setting.setValue('CHECK/access_time', int(self.ui.check_box_access_time.isChecked()))
        self.setting.setValue('CHECK/auto_clear', int(self.ui.check_box_auto_clear.isChecked()))
        self.setting.setValue('PATH/last_open_dir', self.open_dir_path)
        self.setting.setValue('THEME/mode', theme().value)
        event.accept()

    def init_ui(self):
        self.setWindowTitle(APP.software_name_simplified_chinese)  # 设置标题
        self.setWindowIcon(QIcon(APP.software_logo))  # 设置图标
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        # 计算窗口在屏幕中心的位置
        w, h = screen_geometry.width(), screen_geometry.height()
        self.resize(w * 1240 / 1920, h * 500 / 1080)
        self.navigationInterface.setCollapsible(True)
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)
        # 1. 创建启动页面
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(102, 102))
        # 2. 在创建其他子页面前先显示主界面
        self.show()
        # 3. 创建子界面
        loop = QEventLoop(self)
        QTimer.singleShot(300, loop.quit)
        loop.exec()
        # 4. 隐藏启动页面
        self.splashScreen.finish()
        setThemeColor(APP.software_theme_color)  # 设置主题颜色

    def init_table(self):
        self.ui.table_widget_info_bar.setContextMenuPolicy(Qt.CustomContextMenu)  # 打开右键菜单策略
        self.ui.table_widget_info_bar.setBorderRadius(8)
        self.ui.table_widget_info_bar.setWordWrap(False)
        self.ui.table_widget_info_bar.setRowCount(-1)
        self.ui.table_widget_info_bar.setColumnCount(4)
        self.ui.table_widget_info_bar.setColumnWidth(0, 230)
        self.ui.table_widget_info_bar.setHorizontalHeaderLabels(['路径', '创建时间', '修改时间', '访问时间'])
        self.ui.table_widget_info_bar.setBorderVisible(True)
        self.delegate: CustomDelegate = CustomDelegate(self.ui.table_widget_info_bar)  # 将表格功能进行自定义委托
        self.ui.table_widget_info_bar.setItemDelegate(self.delegate)
        self.ui.table_widget_info_bar.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # 该条设置列自适应宽度
        # 该条设置列最小宽度，防止拉伸改变表头宽度的时候，宽度小于最小宽度，以至于表头文字内容消失，显示异常
        self.ui.table_widget_info_bar.horizontalHeader().setMinimumSectionSize(100)
        self.ui.table_widget_info_bar.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.ui.table_widget_info_bar.horizontalHeader().setMaximumSectionSize(400)  # 设置最大宽度为200像素

    def band(self):
        self.ui.push_button_change_time.clicked.connect(self.change_file_time)
        self.ui.tool_button_open_dir.clicked.connect(lambda: self.open_dir_mode(change_mode=UserFormChangeMode.new))
        self.ui.text_edit_path_input.signal_drop.connect(self.drop_mode)
        self.ui.text_edit_path_input.signal_paste.connect(self.paste_mode)
        self.ui.text_edit_path_input.textChanged.connect(
            lambda: self.typing_mode(self.ui.text_edit_path_input.toPlainText()))
        self.ui.table_widget_info_bar.itemClicked.connect(self.set_table)
        self.ui.table_widget_info_bar.cellClicked.connect(self.receive_left_clicked_pos)
        self.ui.table_widget_info_bar.customContextMenuRequested.connect(self.receive_right_clicked_pos)
        self.ui.table_widget_info_bar.itemEntered.connect(self.update_tooltip)
        self.ui.table_widget_info_bar.leaveEvent = self.on_mouse_leave_table
        self.delegate.left_double_click_signal_pos_data.connect(self.receive_left_double_clicked_pos)
        self.ui.calendar_picker_ymd.datePicked.connect(self.receive_global_ymd_time_change)
        self.ui.time_picker_hms.timePicked.connect(self.receive_global_hms_time_change)
        self.dialog.signal_time_data.connect(self.receive_local_time_change)
        self.ui.tool_button_toggle_theme.clicked.connect(lambda: toggleTheme(lazy=True))

    def on_mouse_leave_table(self, e):
        self.ui.table_widget_info_bar.setToolTip('显示填入输入框中文件信息的表格。')

    def receive_local_time_change(self, time: str, pos: tuple, selected_item: dict or None) -> None:
        row, column = pos
        if selected_item:
            time_change_mode = UserFormChangeMode.multiple_local_time
        else:
            time_change_mode = UserFormChangeMode.single_local_time
        self.set_table(change_mode=time_change_mode,
                       data=(time,
                             row,
                             column,
                             selected_item))

    def receive_global_ymd_time_change(self, date: QDate) -> None:
        """
        :param date:
            全局时分秒变量,
            更改到表格中
            同时更新self.file_name和self.file_info
        :return:
        """
        ymd_str = datetime(date.year(), date.month(), date.day()).strftime('%Y年%#m月%#d日')
        if self.file_info:
            self.ui.calendar_picker_ymd.handle_update_time(date=date)
            file_info = self.file_info.copy()
            for path, timestamps in file_info.items():
                if not isinstance(timestamps, list) or len(timestamps) != 3:
                    raise ValueError(f"Incorrect timestamp format for file path '{path}'")
                create_time, modify_time, access_time = timestamps
                # 提取并保留原有的时分秒
                create_hms = create_time.split(' ')[-1]
                modify_hms = modify_time.split(' ')[-1]
                access_hms = access_time.split(' ')[-1]
                # 将新的年月日与旧的时分秒拼接
                if self.ui.check_box_create_time.isChecked():
                    create_time = f"{ymd_str} {create_hms}"
                if self.ui.check_box_modify_time.isChecked():
                    modify_time = f"{ymd_str} {modify_hms}"
                if self.ui.check_box_access_time.isChecked():
                    access_time = f"{ymd_str} {access_hms}"
                file_info[path] = [create_time, modify_time, access_time]
            self.file_info = file_info
            self.set_table(change_mode=UserFormChangeMode.global_time)
        else:
            self.show_message(message='内容为空,请先导入文件。')
            logger.warning('内容为空,没有进行任何更新。')

    def receive_global_hms_time_change(self, time: QTime) -> None:
        """
        :param time:
            全局时分秒变量,
            更改到表格中
            同时更新self.file_name和self.file_info
        :return:
        """
        hms_str = f"{time.hour():02d}:{time.minute():02d}:{time.second():02d}"  # 使用f-string直接格式化时分秒
        if self.file_info:
            self.ui.time_picker_hms.handle_set_time(time)
            file_info = self.file_info.copy()
            for path, timestamps in file_info.items():
                if not isinstance(timestamps, list) or len(timestamps) != 3:
                    raise ValueError(f'文件路径:"{path}"的时间戳格式不正确。')
                create_time, modify_time, access_time = timestamps
                # 提取并保留原有的年月日
                create_ymd = ' '.join(create_time.split(' ')[:-1])
                modify_ymd = ' '.join(modify_time.split(' ')[:-1])
                access_ymd = ' '.join(access_time.split(' ')[:-1])
                # 将新的时分秒与旧的年月日拼接
                if self.ui.check_box_create_time.isChecked():
                    create_time = f"{create_ymd} {hms_str}"
                if self.ui.check_box_modify_time.isChecked():
                    modify_time = f"{modify_ymd} {hms_str}"
                if self.ui.check_box_access_time.isChecked():
                    access_time = f"{access_ymd} {hms_str}"
                file_info[path] = [create_time, modify_time, access_time]
            self.file_info = file_info
            self.set_table(change_mode=UserFormChangeMode.global_time)
        else:
            self.show_message(message='内容为空,请先导入文件。')
            logger.warning('内容为空,没有进行任何更新。')

    def update_tooltip(self, item) -> None:
        """
        更新鼠标悬浮提示
        :param item: 行和列
        :return:
        """
        if item is None:
            return
        row: int = item.row()
        col: int = item.column()
        text_tip = ['鼠标双击此处即可单独修改路径。', '鼠标双击此处即可单独修改时间。']
        tip = ''
        if col == 0:
            tip = text_tip[0]
        elif col in range(1, 4):
            tip = text_tip[1]
        title: str = self.ui.table_widget_info_bar.horizontalHeaderItem(col).text()
        file_path: str = self.ui.table_widget_info_bar.item(row, col).text()

        self.ui.table_widget_info_bar.setToolTip(f'{title}:{file_path} ' + tip)

    def receive_left_double_clicked_pos(self, pos: tuple) -> None:
        """
        接收鼠标左键双击的行、列数据,
        并实时更新到->self.left_double_click_row, self.left_double_click_column,
        实现全局引用。
        并能根据行列不同,触发不同的事件。
            鼠标左键双击路径列(0)->触发修改文件事件(open_dir_mode)
            鼠标左键双击路径列(1-3)->触发修改日期事件(open_time_picker_dialog)
        :param pos:
            类型:tuple
            记录行和列的元祖
        :return:
            None
        """
        self.current_left_double_click_row: int = pos[0]
        self.current_left_double_click_column: int = pos[1]
        logger.info(
            f'{MouseEvent.left_button.double_click} -> [行]:{self.current_left_double_click_row} [列]:{self.current_left_double_click_column}')
        if self.current_left_double_click_column == 0:
            self.open_dir_mode(change_mode=UserFormChangeMode.path, pos=pos)
        elif self.current_left_double_click_column in range(1, 4):
            self.open_time_picker_dialog(pos, change_mode=UserFormChangeMode.single_local_time)

    def receive_left_clicked_pos(self, row: int, column: int) -> None:  # 实时更新点击的行和列
        """
        接收鼠标左键单击的行、列数据,
        并实时更新到->self.current_left_click_row,self.current_left_click_column,
        实现全局引用。
        并能根据行列的不同,触发不同的事件。
        :param row:
            类型:int
            记录行
        :param column:
            类型:int
            记录列
        :return:
            None
        """
        logger.info(f'{MouseEvent.left_button.single_click} -> [行]:{row} [列]:{column}')
        self.current_left_click_row: int = row
        self.current_left_click_column: int = column
        if column == 0:
            ...
            # 定义左键单击路径列事件
        elif column in range(1, 4):
            ...
            # 定义左键单击时间列事件

    def receive_right_clicked_pos(self, pos: tuple) -> None:
        """
        接收鼠标右键单击的行、列数据,
        并实时更新到->self.current_right_click_row,self.current_right_click_column,
        实现全局引用。
        :param pos:
            类型:tuple
            记录行和列的元祖
        :return:
            None
        """
        self.current_right_click_row: int = self.ui.table_widget_info_bar.rowAt(pos.y())  # 获取当前右键的行
        self.current_right_click_column: int = self.ui.table_widget_info_bar.columnAt(pos.x())  # 获取当前右键的列
        logger.info(
            f'{MouseEvent.right_button.single_click} -> [行]:{self.current_right_click_row} [列]:{self.current_right_click_column}')
        path_pos = self.current_right_click_row, 0
        create_time_pos = self.current_right_click_row, 1
        modify_time_pos = self.current_right_click_row, 2
        access_time_pos = self.current_right_click_row, 3
        # 存储用户选择的信息的字典
        selected_items: dict = {}
        self.ui.table_widget_info_bar.setSelectRightClickedRow(pos)  # 设置选中该项
        for i in self.ui.table_widget_info_bar.selectedItems():
            row = i.row()
            col = i.column()
            path_item = self.ui.table_widget_info_bar.item(row, 0)  # 假设路径所在的列是第一列
            if path_item:
                path = path_item.text()
                if path not in selected_items:
                    selected_items[path] = []  # 如果路径不在字典中，则初始化空列表
                if col > 0:  # 如果不是路径列，则将该项的文本添加到对应路径的值列表中
                    selected_items[path].append(i.text())
        selected_num: int = len(selected_items)
        menu = RoundMenu()  # 创建自定义菜单
        menu.addAction(Action(icon=FIF.ADD.icon(), text=self.tr('添加新文件'), parent=self,
                              triggered=lambda: self.open_dir_mode(change_mode=UserFormChangeMode.new)))
        # if self.file_info and self.file_name:
        if selected_num == 1:
            time_change_mode = UserFormChangeMode.single_local_time
            menu.addSeparator()
            menu.addAction(Action(icon=FIF.FOLDER.icon(), text=self.tr('修改文件路径'), parent=self,
                                  triggered=lambda: self.open_dir_mode(change_mode=UserFormChangeMode.path,
                                                                       pos=path_pos)))
            menu.addSeparator()
            menu.addActions([Action(icon=FIF.HISTORY.icon(), text=self.tr('变更创建时间'), parent=self,
                                    triggered=lambda: self.open_time_picker_dialog(pos=create_time_pos,
                                                                                   change_mode=time_change_mode)),
                             Action(icon=FIF.LABEL.icon(), text=self.tr('变更修改时间'), parent=self,
                                    triggered=lambda: self.open_time_picker_dialog(pos=modify_time_pos,
                                                                                   change_mode=time_change_mode)),
                             Action(icon=FIF.ZOOM_OUT.icon(), text=self.tr('变更访问时间'), parent=self,
                                    triggered=lambda: self.open_time_picker_dialog(pos=access_time_pos,
                                                                                   change_mode=time_change_mode))])

        elif selected_num > 1:
            time_change_mode = UserFormChangeMode.multiple_local_time
            menu.addSeparator()
            menu.addActions(
                [Action(icon=FIF.HISTORY.icon(), text=self.tr(f'变更创建时间(选中的{selected_num}项)'), parent=self,
                        triggered=lambda: self.open_time_picker_dialog(pos=create_time_pos,
                                                                       change_mode=time_change_mode,
                                                                       selected_items=selected_items)),
                 Action(icon=FIF.LABEL.icon(), text=self.tr(F'变更修改时间(选中的{selected_num}项)'), parent=self,
                        triggered=lambda: self.open_time_picker_dialog(pos=modify_time_pos,
                                                                       change_mode=time_change_mode,
                                                                       selected_items=selected_items)),
                 Action(icon=FIF.ZOOM_OUT.icon(), text=self.tr(f'变更访问时间(选中的{selected_num}项)'), parent=self,
                        triggered=lambda: self.open_time_picker_dialog(pos=access_time_pos,
                                                                       change_mode=time_change_mode,
                                                                       selected_items=selected_items))])
        elif not selected_num:
            ...
        menu.exec(self.ui.table_widget_info_bar.mapToGlobal(pos))

    @staticmethod
    def get_file_time(file_path: str) -> list:
        """
        得到文件的创建日期,修改日期,访问日期
        :param file_path:
            类型:str
            需要得到日期列表的路径
        :return:
            类型:list
            [创建日期,修改日期,访问日期]
        """
        time_format: str = '%Y年%#m月%#d日 %H:%M:%S'
        create_time: str = datetime.fromtimestamp(os.path.getctime(file_path)).strftime(time_format)
        modify_time: str = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime(time_format)
        access_time: str = datetime.fromtimestamp(os.path.getatime(file_path)).strftime(time_format)
        return [create_time, modify_time, access_time]

    def _process_new_table(self):
        for file_path in self.file_name:
            # 检查当前项是否已经存在于表格中
            exists: bool = False
            for row in range(self.ui.table_widget_info_bar.rowCount()):
                item: QTableWidgetItem = self.ui.table_widget_info_bar.item(row, 0)
                if item is not None and item.text() == file_path:
                    exists: bool = True
                    break
            # 如果当前项不存在于表格中，则添加
            if not exists:
                row_position = self.ui.table_widget_info_bar.rowCount()
                self.ui.table_widget_info_bar.insertRow(row_position)
                # 添加路径
                path_item = QTableWidgetItem(file_path)
                self.ui.table_widget_info_bar.setItem(row_position, 0, path_item)
                # 获取文件的创建时间、修改时间和访问时间
                file_stat = os.stat(file_path)
                create_time, modify_time, access_time = APP.get_file_time(file_path)
                create_time_item: QTableWidgetItem = QTableWidgetItem(create_time)
                modify_time_item: QTableWidgetItem = QTableWidgetItem(modify_time)
                access_time_item: QTableWidgetItem = QTableWidgetItem(access_time)
                self.ui.table_widget_info_bar.setItem(row_position, 1, create_time_item)
                self.ui.table_widget_info_bar.setItem(row_position, 2, modify_time_item)
                self.ui.table_widget_info_bar.setItem(row_position, 3, access_time_item)
                self.file_info[file_path] = [create_time, modify_time, access_time]
                self.ui.table_widget_info_bar.scrollToItem(path_item)
                self.ui.table_widget_info_bar.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
                self.ui.table_widget_info_bar.horizontalHeader().setMaximumSectionSize(400)  # 设置最大宽度为200像素

    def set_table(self, change_mode: UserFormChangeMode = UserFormChangeMode.new,
                  **kwargs: Optional[tuple]) -> None:  # 增
        if change_mode == UserFormChangeMode.new:
            self._no_signal_change_text()
            self._process_new_table()
        elif change_mode == UserFormChangeMode.path:
            new_path, row, column = kwargs['data']
            if new_path:
                new_path = os.path.normpath(new_path)  # 格式化路径
                # 获取替换文件的时间
                create_time, modify_time, access_time = self.get_file_time(new_path)
                # 通过当前点击行列数来获取当前第一列的路径数据
                path: str = self.ui.table_widget_info_bar.item(row, 0).text()  # 获取原来列表的键
                for old_key in list(self.file_info.keys()):
                    if old_key == path:
                        self.file_info.pop(old_key)
                        self.file_name.remove(old_key)
                        self.file_info[new_path] = [create_time, modify_time, access_time]
                        self.file_name.append(new_path)
                        break
                self._no_signal_change_text()
                # 将字符串转换为Qtable对象
                create_time_item: QTableWidgetItem = QTableWidgetItem(create_time)
                modify_time_item: QTableWidgetItem = QTableWidgetItem(modify_time)
                access_time_item: QTableWidgetItem = QTableWidgetItem(access_time)
                new_path_item: QTableWidgetItem = QTableWidgetItem(new_path)
                self.ui.table_widget_info_bar.setItem(row, 0, new_path_item)
                self.ui.table_widget_info_bar.setItem(row, 1, create_time_item)
                self.ui.table_widget_info_bar.setItem(row, 2, modify_time_item)
                self.ui.table_widget_info_bar.setItem(row, 3, access_time_item)
                self.local_change_flag = False if len(self.file_info) else self.local_change_flag
                logger.success(
                    f'[行]:{row} [列]:{column} [{TableRange.path.only_text()}][发生改变]:"{path}" -> "{new_path}"')

        elif change_mode == UserFormChangeMode.single_local_time:
            self.local_change_flag = True
            new_time, row, column, _ = kwargs.get('data')
            old_time = self.ui.table_widget_info_bar.item(row, column).text()
            if new_time != old_time:
                item_ymd_hms = QTableWidgetItem(new_time)  # 转化为QTableWidgetItem对象
                self.ui.table_widget_info_bar.setItem(row, column, item_ymd_hms)  # 更新到面板中
                # 更新file_info字典
                self.file_info.update(self._get_all_items())
                self.local_change_create_time_flag = True if column == 1 else False
                logger.success(
                    f'[行]:{row} [列]:{column} [路径]:"{self.ui.table_widget_info_bar.item(row, 0).text()}" [{TableRange.get_text(column)}][发生改变]:{old_time} -> {new_time}')
        elif change_mode == UserFormChangeMode.multiple_local_time:
            self.local_change_flag = True
            new_time, _, column, selected_items = kwargs.get('data')
            rows: list = [self._find_table_row_by_path(p) for p in list(selected_items.keys())]
            at_least_one = False  # 至少改变过一次的标签
            for row_index in rows:
                old_time = self.ui.table_widget_info_bar.item(row_index, column).text()
                if new_time != old_time:
                    at_least_one = True if not at_least_one else at_least_one
                    item_ymd_hms = QTableWidgetItem(new_time)  # 转化为QTableWidgetItem对象
                    self.ui.table_widget_info_bar.setItem(row_index, column, item_ymd_hms)  # 更新到面板中
                    logger.success(
                        f'[行]:{row_index} [列]:{column} [路径]:"{self.ui.table_widget_info_bar.item(row_index, 0).text()}" [{TableRange.get_text(column)}][发生改变]:{old_time} -> {new_time}')
            # 更新file_info字典
            self.file_info.update(self._get_all_items())
            self.local_change_create_time_flag = True if column == 1 else self.local_change_create_time_flag
        elif change_mode == UserFormChangeMode.global_time:
            self.global_change_flag = True
            nt = []
            at_least_one = False  # 至少改变过一次的标签
            # 获取最新的文件信息字典
            current_info_bar: dict = self._get_all_items()
            # 更新info_bar中与self.file_info有差异的条目
            for path, new_time in self.file_info.items():
                if path in current_info_bar:
                    at_least_one = True if not at_least_one else at_least_one
                    nt = new_time
                    current_info_bar[path] = new_time
                    row_index = self._find_table_row_by_path(path)
                    if row_index is not None:
                        for col_index, timestamp in enumerate(new_time, start=1):
                            item = QTableWidgetItem(timestamp)
                            self.ui.table_widget_info_bar.setItem(row_index, col_index, item)
                    else:
                        logger.warning(f'在表中找不到{path}的行。')
                else:
                    logger.warning(f'在表中找不到self.file_info的路径"{path}"。')
            if at_least_one:
                _text = ''
                _new_time = []
                if self.ui.check_box_create_time.isChecked():
                    _text += f'[{TableRange.create_time.only_text()}]'
                    _new_time.append(nt[0])
                if self.ui.check_box_modify_time.isChecked():
                    _text += f'[{TableRange.modify_time.only_text()}]'
                    _new_time.append(nt[1])
                if self.ui.check_box_access_time.isChecked():
                    _text += f'[{TableRange.access_time.only_text()}]'
                    _new_time.append(nt[2])
                logger.success(
                    f'[全局时间] [发生改变]:{_text} -> {_new_time}')

    def show_message(self, message, title='提示'):
        MessageBox(title=title, content=message, parent=self).exec()

    def _find_table_row_by_path(self, path: str) -> Optional[int]:
        """
        通过路径查找其表格中所在的行
        :param path:
            类型:字符串
            传入有效且表中存在的路径
        :return:
            类型:整数
            返回传入路径的所在行
        """
        total_rows = self.ui.table_widget_info_bar.rowCount()
        for row_index in range(total_rows):
            path_item = self.ui.table_widget_info_bar.item(row_index, 0)
            if path_item is not None and path_item.text() == path:
                return row_index
        return None

    def delete_content(self, content_to_delete: str) -> None:  # 删除对应内容的项
        # 查找需要删除的项的行索引
        row_index: int = -1
        for row in range(self.ui.table_widget_info_bar.rowCount()):
            item = self.ui.table_widget_info_bar.item(row, 0)  # 假设内容在第一列
            if item.text() == content_to_delete:
                row_index = row
                break
        if row_index != -1:
            # 删除行
            self.ui.table_widget_info_bar.removeRow(row_index)
            logger.success(f'[已删除]: {content_to_delete}')
            # 从文件名列表中也移除
            self.file_name.remove(content_to_delete)
            self.file_info.pop(content_to_delete)
            self.ui.table_widget_info_bar.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        else:
            logger.error(f'要删除的内容"{content_to_delete}"未找到!')

    def _get_all_items(self):
        # 获取行数和列数
        total_rows: int = self.ui.table_widget_info_bar.rowCount()  # 行
        # 初始化字典，用于存储文件路径及其对应的时间戳
        all_items: dict = {}
        # 遍历所有行
        for row in range(total_rows):
            # 初始化当前行的字典项
            # 依次获取文件路径、创建时间、修改时间和访问时间
            for column in range(4):
                item: QTableWidgetItem = self.ui.table_widget_info_bar.item(row, column)
                if item is not None:
                    text = item.text()
                    if column == 0:  # 文件路径
                        current_row_key = text
                    else:  # 时间戳
                        if current_row_key not in all_items:
                            all_items[current_row_key] = []
                        all_items[current_row_key].append(text)
        return all_items

    def _no_signal_change_text(self):
        self.ui.text_edit_path_input.textChanged.disconnect()
        self.ui.text_edit_path_input.setText('\n'.join(self.file_name) if self.file_name else '')
        self.ui.text_edit_path_input.textChanged.connect(
            lambda: self.typing_mode(self.ui.text_edit_path_input.toPlainText()))

    def is_duplicate_file(func):
        def wrapper(self, *args, **kwargs):
            result: list = func(self, *args, **kwargs)
            if len(result) < 10:
                self.show_message('\n'.join(list(set(result)))) if result else 0
            else:
                self.show_message('检测到多数文件重复,已自动为您过滤!')

        return wrapper

    def open_time_picker_dialog(self, pos, change_mode: UserFormChangeMode, **kwargs):
        q_format = "yyyy年M月d日 H:mm:ss"  # 定义转换成QDateTime类型的格式
        self.dialog.set_position(pos)  # 设置需要发送的位置
        row, column = pos
        if change_mode == UserFormChangeMode.single_local_time:  # 此时select_item字典长度为1
            self.dialog.init_sec_table(row=3, column=1)  # 初始化表格
            path = self.ui.table_widget_info_bar.item(row, 0).text()  # 得到路径
            setting_create_time, setting_modify_time, setting_access_time = \
                (
                    self.ui.table_widget_info_bar.item(row, 1).text(),
                    self.ui.table_widget_info_bar.item(row, 2).text(),
                    self.ui.table_widget_info_bar.item(row, 3).text()
                )  # 得到点击的设置时间
            file_name = os.path.basename(path)  # 根据路径得到文件名
            self.dialog.sd.table_widget_sec_info_bar.setItem(0, 0, QTableWidgetItem(file_name))  # 设置路径到表格中
            create_time, modify_time, access_time = self.get_file_time(file_path=path)  # 得到实际的日期信息
            actual_time: str = ''
            setting_time: str = ''
            actual_time_type: str = ''
            setting_time_type: str = ''
            actual_status = StatusInfo.actual
            setting_status = StatusInfo.setting
            if column == TableRange.create_time.value:
                actual_time: str = TableRange.create_time.status_text(actual_status)
                setting_time: str = TableRange.create_time.status_text(setting_status)
                actual_time_type: str = create_time
                setting_time_type: str = setting_create_time
            elif column == TableRange.modify_time.value:
                actual_time: str = TableRange.modify_time.status_text(actual_status)
                setting_time: str = TableRange.create_time.status_text(setting_status)
                actual_time_type: str = modify_time
                setting_time_type: str = setting_modify_time
            elif column == TableRange.access_time.value:
                actual_time: str = TableRange.access_time.status_text(actual_status)
                setting_time: str = TableRange.create_time.status_text(setting_status)
                actual_time_type: str = access_time
                setting_time_type: str = setting_access_time
            self.dialog.sd.table_widget_sec_info_bar.setToolTip(
                '\n'.join([
                    f'[{TableRange.file_name.only_text()}]:{file_name}',
                    f'[{TableRange.path.status_text(StatusInfo.current)}]:{path}]',
                    f'[{TableRange.create_time.status_text(actual_status)}]:{create_time}',
                    f'[{TableRange.modify_time.status_text(actual_status)}]:{modify_time}',
                    f'[{TableRange.access_time.status_text(actual_status)}]:{access_time}',
                    f'[{TableRange.create_time.status_text(setting_status)}]:{setting_create_time}',
                    f'[{TableRange.modify_time.status_text(setting_status)}]:{setting_modify_time}',
                    f'[{TableRange.access_time.status_text(setting_status)}]:{setting_access_time}']))  # 设置鼠标悬浮提示
            # 获取点击的内容的时间
            q_time: QDateTime = QDateTime.fromString(setting_time_type, q_format)
            self.dialog.sd.calendar_picker_ymd.setDate(q_time.date())
            self.dialog.sd.time_picker_hms.setTime(q_time.time())  # 设置与点击内容一致的时间
            self.dialog.setWindowTitle(actual_time.replace(StatusInfo.actual.text(), StatusInfo.change.text()))  # 设置标题
            self.dialog.sd.table_widget_sec_info_bar.setVerticalHeaderItem(1, QTableWidgetItem(actual_time))  # 添加列的名字
            self.dialog.sd.table_widget_sec_info_bar.setItem(1, 0, QTableWidgetItem(actual_time_type))  # 设置实际时间
            self.dialog.sd.table_widget_sec_info_bar.setVerticalHeaderItem(2, QTableWidgetItem(setting_time))  # 添加列的名字
            self.dialog.sd.table_widget_sec_info_bar.setItem(2, 0, QTableWidgetItem(setting_time_type))
            self.dialog.sd.table_widget_sec_info_bar.setVerticalHeaderItem(2, QTableWidgetItem(setting_time))
            self.dialog.exec()
        elif change_mode == UserFormChangeMode.multiple_local_time:  # 此时select_item字典长度大于1
            self.dialog.init_sec_table(row=1, column=1)
            selected_items: dict = kwargs.get('selected_items')
            self.dialog.set_selected_items(selected_items)  # 设置需要发送的用户所选项的字典
            actual_time: str = ''
            actual_status = StatusInfo.actual
            if column == TableRange.create_time.value:
                actual_time: str = TableRange.create_time.status_text(actual_status)
            elif column == TableRange.modify_time.value:
                actual_time: str = TableRange.modify_time.status_text(actual_status)
            elif column == TableRange.access_time.value:
                actual_time: str = TableRange.access_time.status_text(actual_status)
            # 遍历字典中的文件信息{路径:[创建时间,修改时间,访问时间]}
            self.dialog.setWindowTitle(actual_time.replace(StatusInfo.actual.text(), StatusInfo.change.text()))  # 设置标题
            paths: list = [p for p in list(selected_items.keys())]
            file_names: list = [os.path.basename(p) for p in paths]
            self.dialog.sd.table_widget_sec_info_bar.setItem(0, 0, QTableWidgetItem(' '.join(file_names)))  # 设置路径到表格中
            self.dialog.sd.table_widget_sec_info_bar.setToolTip(
                '\n'.join(
                    f"[{i + 1}]:[{TableRange.file_name.status_text(StatusInfo.current)}]:{file_names[i]} [{TableRange.path.only_text()}]:{paths[i]}"
                    for i in range(len(paths))))
            self.dialog.exec()

    @is_duplicate_file
    def open_dir_mode(self, change_mode=UserFormChangeMode.new, **kwargs):  # 打开文件夹模式
        duplicate_file: list = []
        self.open_dir_path = APP.default_path if not os.path.isdir(self.open_dir_path) else self.open_dir_path
        if change_mode == UserFormChangeMode.new:
            data: list = [os.path.normpath(i) for i in
                          QFileDialog.getOpenFileNames(self, "选择文件", self.open_dir_path, "All Files (*)")[
                              0]]
            self.open_dir_path = os.path.dirname(os.path.normpath(data[-1])) if data else self.open_dir_path
            if self.file_name:
                for i in data:
                    if i.lower() not in [f.lower() for f in self.file_name]:
                        self.file_name.append(i)
                    else:
                        duplicate_file.append(f'"{i}"已存在!')
                        logger.warning(f'"{i}"已存在!')
            else:
                self.file_name = data
            self.set_table(change_mode=change_mode)
        elif change_mode == UserFormChangeMode.path:
            # todo:当前有项才能选择
            if self.file_info:  # 首先判断表中要有项
                pos: tuple = kwargs['pos']  # 再得到鼠标选择的表格位置
                new_key: str = QFileDialog.getOpenFileName(self, "选择文件", self.open_dir_path, "All Files (*)")[0]
                # 加入对项中已存在的文件进行判断
                if os.path.normpath(new_key) in self.file_name:
                    duplicate_file.append(f'"{new_key}"已存在!')
                    logger.warning(f'{new_key}已存在!')
                else:
                    data: tuple = new_key, pos[0], pos[1]
                    self.set_table(change_mode=change_mode, data=data)
            else:
                logger.error(self.tr('未选择任何项!'))
        return duplicate_file

    def drop_mode(self, all_path, new_path) -> list:  # 拖入模式
        for i in all_path:
            if i.lower() not in [f.lower() for f in self.file_name]:
                self.file_name.append(i)
        self.set_table(change_mode=UserFormChangeMode.new)

    def paste_mode(self, all_path: str, new_path) -> None:
        if self.file_name:
            for i in all_path:
                if i.lower() not in [f.lower() for f in self.file_name]:
                    self.file_name.append(i)
        else:
            self.file_name = all_path
        self.set_table(change_mode=UserFormChangeMode.new)

    def typing_mode(self, res) -> list:
        # 检查用户是否完成了输入
        file_names: list = res.rstrip('\n').split('\n')
        if res and res.endswith('\n'):
            # 以 '\n' 分隔文本
            # 遍历分隔后的文件名
            for file_name in file_names:
                # 去除首尾空白字符
                file_name = file_name.strip()
                # 如果文件名存在，并且不在列表中，则添加到列表中
                if file_name and os.path.isfile(file_name) and file_name.lower() not in [f.lower() for f in
                                                                                         self.file_name]:
                    self.file_name.append(os.path.normpath(file_name))

            # 存储路径
            self._process_new_table()
            logger.info(f'手动输入内容发生改变:"{self.file_name}"')
        else:
            need_remove: list = [f for f in self.file_name if f not in file_names]
            for item in need_remove:
                self.delete_content(item)
            self._process_new_table()

    def checker(func):
        def wrapper(self, *args, **kwargs):
            path: str = self.ui.text_edit_path_input.toPlainText().strip()  # 去除首尾空白字符
            # 用于显示错误消息的统一函数
            if not self.file_name:
                if not path:
                    self.show_message('内容为空!')
                else:
                    self.show_message('没有找到有效文件路径!')
                return
            if not self.local_change_flag:
                if not self.global_change_flag:
                    self.show_message('至少选择一个年月日或时分秒!')
                    return
            # 执行原函数
            result = func(self, *args, **kwargs)
            res_info = []
            error_info: dict = {}
            for i in result.items():
                res_info.append(i)
            for j in res_info:
                if j[1][0] is False:
                    error_info[j[0]] = f'{j[1][1]}'
            ei = '\n'.join([f'文件"{os.path.basename(j[0])}" 原因:[{j[1]}]' for j in error_info.items()])
            title = '修改结果'
            if error_info:
                message = f'找到如下错误信息:\n{ei}'
                message += '\n其余全部修改成功。' if len(self.file_info) - len(error_info) >= 1 else ''
                self.show_message(title=title, message=message)
            else:
                self.show_message(title=title, message=f'修改成功')
            # 更新局部提交flag
            self.local_change_flag = False
            self.global_change_flag = False
            self.local_change_create_time_flag = self.local_change_flag
            self.ui.calendar_picker_ymd.init_setting()
            self.ui.time_picker_hms.init_setting(showSeconds=True)
            if self.ui.check_box_auto_clear.isChecked():
                self.ui.text_edit_path_input.setText(None)

        return wrapper

    @checker
    def change_file_time(self):
        result: dict = {}
        for file_name, time_info in self.file_info.items():
            create_time, modify_time, access_time = time_info
            create_time_stamp = datetime.strptime(create_time, '%Y年%m月%d日 %H:%M:%S').timestamp()
            modify_time_stamp = datetime.strptime(modify_time, '%Y年%m月%d日 %H:%M:%S').timestamp()
            access_time_stamp = datetime.strptime(access_time, '%Y年%m月%d日 %H:%M:%S').timestamp()
            _file_path, _result, _reason = self._change_file_time(file_path=file_name, create_time=create_time_stamp,
                                                                  modify_time=modify_time_stamp,
                                                                  access_time=access_time_stamp)
            result[_file_path] = [_result, _reason]
        return result

    def _change_file_time(self, file_path: str, create_time: float, modify_time: float, access_time: float):
        """
        用来修改任意文件的相关时间属性，时间格式：时间戳
        :param file_path: 文件路径名
        :param create_time: 创建时间（时间戳）
        :param modify_time: 修改时间（时间戳）
        :param access_time: 访问时间（时间戳）
        """
        result: bool = False
        reason = None
        try:
            fh = CreateFile(file_path, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, 0)
            create_time = datetime.fromtimestamp(create_time)
            access_time = datetime.fromtimestamp(access_time)
            modify_time = datetime.fromtimestamp(modify_time)
            SetFileTime(fh, create_time, access_time, modify_time)
            CloseHandle(fh)
            result = True
        except Exception as error:

            try:
                os.utime(path=file_path, times=(access_time, modify_time))
            except Exception as e:
                reason = e
            if self.local_change_create_time_flag:
                logger.error(self.local_change_create_time_flag)
                reason = f'无法变更"{os.path.splitext(os.path.basename(file_path))[1]}"格式的创建时间!'
                reason += f' {error}' if error else ''
            elif self.ui.check_box_create_time.isChecked() and not self.local_change_flag:
                reason = f'无法变更"{os.path.splitext(os.path.basename(file_path))[1]}"格式的创建时间!'
                reason += f' {error}' if error else ''
            else:
                result = True
        finally:
            return file_path, result, reason

    @staticmethod
    def setDpiFromWindowsSettings():
        """
        根据windows的DPI缩放来适配软件的DPI
        :return:
        """
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Unset)


logger.add(
    os.path.join(APP.log_path),
    rotation="10 MB",
    retention="10 days",
    level="DEBUG",
)

if __name__ == "__main__":
    APP.setDpiFromWindowsSettings()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    translator = QTranslator()
    translator.load(QLocale.system(), ":/lan/qfluentwidgets_")
    app.installTranslator(translator)
    w = APP()
    w.show()
    sys.exit(app.exec())
