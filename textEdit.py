import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QComboBox
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QToolTip
from PyQt5.QtGui import QFont
import sqlite3
from PyQt5 import uic

W_COEFF = 18.75
FONT_SIZES = [8, 12, 14, 16, 20, 22, 24]
Y_COEFFS = {8: 3, 12: 2.4, 14: 2.1, 16: 2, 20: 1.8, 22: 1.6, 24: 1.5}


class Word:
    def __init__(self, word):
        self.word = word

    def __str__(self):
        return self.word

    def __len__(self):
        return len(self.word)

    def distance(self, word1):
        word2 = str(word1).lower()
        word1 = self.word.lower()
        n, m = len(word1), len(word2)
        if n > m:
            word1, word2 = word2, word1
            n, m = m, n
        curr_row = range(n + 1)
        for i in range(1, m + 1):
            prev_row, curr_row = curr_row, [i] + [0] * n
            for j in range(1, n + 1):
                add, delete, change = prev_row[j] + 1, \
                    curr_row[j - 1] + 1, \
                    prev_row[j - 1]
                if word1[j - 1] != word2[i - 1]:
                    change += 1
                curr_row[j] = min(add, delete, change)
        return curr_row[n]

    def get_find_data(self):
        last_letter = self.word[-1]
        mid_letter = self.word[len(self.word) // 2]
        first_letter = self.word[0]
        return first_letter.lower(), mid_letter.lower(), last_letter.lower()

    def create_similar_words_index(self, sim_words):
        sim_words_index = {
            word[0]: self.distance(word[0]) for word
            in sim_words}
        return sim_words_index

    def sim_registr(self, word1):
        if self.is_capitalize():
            return word1.capitalize()
        return word1.lower()

    def is_capitalize(self):
        return self.word == self.word.capitalize()


class TextEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('designTextEditor.ui', self)
        self.initUI()

    def initUI(self):
        self.write_field.setStyleSheet('border: 0px')

        self.possible_words = QComboBox(self)
        self.possible_words.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.possible_words.setFixedWidth(W_COEFF * self.get_font_size())
        self.setWindowTitle('Текстовый редактор 0.1')
        self.write_field.textChanged.connect(self.advice_words)
        self.write_field.cursorPositionChanged.connect(
            self.hide_clear_recommends)
        self.possible_words.textActivated.connect(
            self.change_wrote_word_to_recommend)
        self.open_btn.triggered.connect(self.open_file)
        self.save_btn.triggered.connect(self.save_file_with_rewrite)
        self.append_btn.triggered.connect(self.save_file_with_append)
        self.close_btn.triggered.connect(self.close_file)
        self.incr_font_btn.triggered.connect(self.incr_font_size)
        self.decr_font_btn.triggered.connect(self.decr_font_size)
        self.font_index = 0
        self.is_file_opened = False
        self.possible_words.hide()

    def get_current_text(self):
        return self.write_field.toPlainText()

    def set_font_size(self):
        size = FONT_SIZES[self.font_index]
        font = QFont()
        self.font_index = FONT_SIZES.index(size)
        font.setPointSize(size)
        self.write_field.setFont(font)
        self.possible_words.setFont(font)
        self.possible_words.setFixedWidth(W_COEFF * self.get_font_size())
        self.possible_words.hide()
        self.update_possible_words()

    def get_cursor_pos(self):
        return self.write_field.textCursor().position()

    def incr_font_size(self):
        if self.font_index < len(FONT_SIZES) - 1:
            self.font_index += 1
        self.set_font_size()

    def decr_font_size(self):
        if self.font_index > 0:
            self.font_index -= 1
        self.set_font_size()

    def get_font_size(self):
        return self.write_field.font().pointSize()

    def find_left_right_space_group_indexes(self, wrote_text, cur_index):
        left_space_index = (' ' + wrote_text[:cur_index]).rfind(' ')
        right_space_index = (wrote_text[cur_index:] + ' ').find(' ')
        left_tab_index = (' ' + wrote_text[:cur_index]).rfind('\t')
        right_tab_index = (wrote_text[cur_index:] + ' ').find('\t')
        left_transf_index = (' ' + wrote_text[:cur_index]).rfind('\n')
        right_transf_index = (wrote_text[cur_index:] + ' ').find('\n')
        if right_space_index != -1:
            right_space_index += cur_index
        if right_tab_index != -1:
            right_tab_index += cur_index
        if right_transf_index != -1:
            right_transf_index += cur_index
        left_space_group_index = max(
            left_space_index, left_tab_index, left_transf_index)
        right_space_group_index = min(
            filter(lambda x: x != -1, [right_space_index, right_tab_index, right_transf_index]))
        return left_space_group_index, right_space_group_index

    def advice_words(self):
        wrote_text = self.get_current_text()

        if wrote_text and not wrote_text[-1].strip():
            self.hide_clear_recommends()
            return -1
        cur_index = self.write_field.textCursor().position()

        self.left_space_index, self.right_space_index = self.find_left_right_space_group_indexes(
            wrote_text, cur_index)

        self.last_typed_word = wrote_text[self.left_space_index: self.right_space_index]

        if not self.last_typed_word:
            self.hide_clear_recommends()
            return -1
        self.last_typed_word = Word(self.last_typed_word)

        if len(self.last_typed_word) > 30 or not self.last_typed_word:
            self.hide_clear_recommends()
            return -1
        find_data = self.last_typed_word.get_find_data()
        con = sqlite3.connect('words_db.sqlite')
        cur = con.cursor()
        first_let, mid_let, last_let = find_data
        sim_words = cur.execute(
            'SELECT word FROM words WHERE (firstLetter=? \
            AND midLetter=? AND lastLetter=?) OR \
            (firstLetter=? AND lastLetter=?) OR \
            (midLetter=? AND lastLetter=?) OR (midLetter=? AND firstLetter=?)',
            (first_let, mid_let, last_let, first_let, last_let, mid_let,
             last_let, mid_let, first_let))

        try:
            sim_words_index = self.last_typed_word.create_similar_words_index(
                sim_words)
            con.close()
            sim_words = self.handle_sim_words_index(sim_words_index)
            self.show_recommended_words(sim_words)

        except ValueError:
            self.hide_clear_recommends()

    def hide_clear_recommends(self):
        self.last_typed_word = ''
        self.possible_words.hide()
        self.possible_words.clear()

    def change_wrote_word_to_recommend(self):
        current_cursor = self.write_field.textCursor()

        wrote_text = self.get_current_text()
        pre_replace_part = wrote_text[:self.left_space_index]

        after_replace_part = wrote_text[self.right_space_index:]

        new_text = pre_replace_part + self.sender().currentText() + after_replace_part
        self.write_field.clear()

        self.write_field.setPlainText(new_text)
        self.write_field.setTextCursor(current_cursor)

    def get_wrote_text_len(self):
        return len(self.get_current_text())

    def handle_sim_words_index(self, sim_words_index):
        sim_words = sorted(sim_words_index.items(), key=lambda p: (p[1], p[0]))
        sim_words = list(map(lambda p: self.last_typed_word.sim_registr(p[0]),
                             sim_words))
        sim_words.insert(0, str(self.last_typed_word))
        return sim_words

    def show_recommended_words(self, sim_words):
        self.update_possible_words()
        self.possible_words.addItems(sim_words)
        self.possible_words.show()

    def update_possible_words(self):
        cursor_rect = self.write_field.cursorRect()
        x = cursor_rect.x()
        current_font_size = FONT_SIZES[self.font_index]
        y = cursor_rect.y() + cursor_rect.height() * \
            Y_COEFFS[current_font_size]

        self.possible_words.move(x, y)
        self.possible_words.update()

    def open_file(self):
        self.fname = QFileDialog.getOpenFileName(self,
                                                 'Open File', '', '*.txt')[0]
        if not self.fname:
            return -1
        self.is_file_opened = True
        with open(self.fname, mode='r', encoding='utf-8') as f:
            text = f.read()
        answer = QMessageBox.question(self, 'File open', 'Rewrite data from changed file?',
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer == QMessageBox.Yes:
            self.write_field.setPlainText(text)

    def save_file_with_rewrite(self):
        if self.is_file_opened:
            with open(self.fname, mode='w', encoding='utf-8') as f:
                f.writelines(self.get_current_text())
        else:
            self.show_file_error()

    def save_file_with_append(self):
        if self.is_file_opened:
            with open(self.fname, mode='a', encoding='utf-8') as f:
                f.writelines(self.get_current_text())
        else:
            self.show_file_error()

    def close_file(self):
        if self.is_file_opened:
            answer = QMessageBox.question(self, 'Confirm file close', 'Are You sure You want to close the file?',
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if answer == QMessageBox.Yes:
                self.is_file_opened = False

    def show_file_error(self):
        answer = QMessageBox.question(self, 'File error', 'File doesn"t open. Open File?',
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer == QMessageBox.Yes:
            self.open_file()

    def closeEvent(self, event):
        close_window = QMessageBox(self)
        close_window.setIcon(QMessageBox.Question)
        close_window.setText('Close Editor?')
        close_window.setWindowTitle('Confirm Exit')
        close_btn = close_window.addButton('Close', QMessageBox.AcceptRole)
        cancel_btn = close_window.addButton('Cancel', QMessageBox.RejectRole)
        if self.is_file_opened:
            close_save_btn = close_window.addButton(
                'Close and Save', QMessageBox.ApplyRole)
            close_window.exec()
            if close_window.clickedButton() == close_save_btn:
                if self.is_file_opened:
                    self.save_file_with_rewrite()
            elif close_window.clickedButton() == cancel_btn:
                event.ignore()
        else:
            close_window.exec()
            if close_window.clickedButton() == cancel_btn:
                event.ignore()

    def keyPressEvent(self, event):
        if event.text() == '=':
            self.incr_font_size()
        elif event.text() == '-':
            self.decr_font_size()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    te = TextEditor()
    te.show()
    sys.exit(app.exec())
