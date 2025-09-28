#!/usr/bin/env python
# coding: utf-8

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from collections import deque
import sys
import os
import json
import hashlib

# 延迟导入pandas，只在需要时加载
try:
    import pandas as pd
except ImportError:
    pd = None

class Vocabulary:
    def __init__(self, word, definition, tag="", learned=False):
        self.word = word
        self.definition = definition
        self.tag = tag.upper()  # 标签字符串，由'L','M','H'组成（大写）
        self.learned = learned  # 是否已学习
        self.original_word = word  # 存储原始单词，用于在文件中定位
        self.original_definition = definition  # 存储原始释义
    
    def to_dict(self):
        """将单词对象转换为字典，便于序列化"""
        return {
            'word': self.word,
            'definition': self.definition,
            'tag': self.tag,
            'learned': self.learned
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建单词对象"""
        return cls(data['word'], data['definition'], data['tag'], data['learned'])

class VocabularyTrainer:
    def __init__(self, a=5, b=10):
        self.to_learn = deque()  # 待学习队列
        self.learned = []        # 已学习队列
        self.a = a  # L选项插入位置
        self.b = b  # M选项插入位置
        self.filename = ""  # 当前加载的文件名
        self.progress_file = ""  # 进度文件名
        self.previous_word = None  # 存储上一个单词
        self.current_word = None   # 存储当前单词
        self.next_word = None      # 存储下一个单词
    
    def get_file_hash(self, filename):
        """计算文件的哈希值，用于识别文件是否改变"""
        hash_md5 = hashlib.md5()
        with open(filename, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def load_from_file(self, filename):
        """从文件加载单词"""
        self.filename = filename
        self.progress_file = os.path.splitext(filename)[0] + ".progress"
        
        # 尝试加载进度文件
        if self.load_progress():
            return  # 成功加载进度，直接返回
        
        # 没有进度文件或文件已改变，从原始文件加载
        try:
            # 检查文件扩展名
            if filename.endswith('.xlsx') or filename.endswith('.xls'):
                # 读取Excel文件
                df = pd.read_excel(filename)
                # 假设第一列是单词，第二列是释义
                for _, row in df.iterrows():
                    word = str(row[0])
                    definition = str(row[1]) if len(row) > 1 else ""
                    self.to_learn.append(Vocabulary(word, definition, tag=""))
            else:
                # 文本文件格式
                with open(filename, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.strip().split('\t')
                        if len(parts) >= 1:
                            word = parts[0]
                            definition = '\t'.join(parts[1:]) if len(parts) > 1 else ""
                            self.to_learn.append(Vocabulary(word, definition, tag=""))
        except FileNotFoundError:
            messagebox.showerror("错误", f"文件 {filename} 未找到")
            sys.exit(1)
        except Exception as e:
            messagebox.showerror("错误", f"读取文件时出错: {e}")
            sys.exit(1)
    
    def load_progress(self):
        """尝试加载进度文件"""
        if not os.path.exists(self.progress_file):
            return False  # 进度文件不存在
        
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 检查文件是否改变
                if data.get('file_hash') != self.get_file_hash(self.filename):
                    return False  # 文件已改变，需要重新加载
                
                # 加载参数
                self.a = data.get('a', 5)
                self.b = data.get('b', 10)
                
                # 加载单词队列
                self.to_learn = deque()
                self.learned = []
                
                for word_data in data.get('to_learn', []):
                    self.to_learn.append(Vocabulary.from_dict(word_data))
                
                for word_data in data.get('learned', []):
                    self.learned.append(Vocabulary.from_dict(word_data))
                
                return True
        except Exception as e:
            print(f"加载进度文件失败: {e}")
            return False
    
    def save_progress(self):
        """保存当前进度到文件"""
        if not self.progress_file:
            return
        
        try:
            data = {
                'file_hash': self.get_file_hash(self.filename),
                'a': self.a,
                'b': self.b,
                'to_learn': [word.to_dict() for word in self.to_learn],
                'learned': [word.to_dict() for word in self.learned]
            }
            
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存进度文件失败: {e}")
    
    def get_continuous_h_count(self, tag):
        """计算标签末尾连续'H'的数量"""
        count = 0
        for char in reversed(tag):
            if char == 'H':
                count += 1
            else:
                break
        return count
    
    def calculate_h_position(self, tag):
        """计算选择H时的插入位置"""
        # 获取连续H的数量
        h_count = self.get_continuous_h_count(tag)
        
        # 找到连续H之前的第一个非H字符及其位置
        non_h_index = len(tag) - h_count - 1
        if non_h_index < 0:  # 如果整个标签都是H
            non_h_char = 'L'  # 默认使用L的基数
        else:
            non_h_char = tag[non_h_index]
        
        # 计算插入位置
        base = self.a if non_h_char == 'L' else self.b
        
        # 计算乘积
        product = 1
        for i in range(2, h_count + 2):
            product *= i
        
        return base * product
    
    def get_next_word(self):
        """获取下一个单词"""
        if not self.to_learn:
            return None
        
        # 保存当前单词为上一个单词
        self.previous_word = self.current_word
        
        # 获取下一个单词
        self.current_word = self.to_learn.popleft()
        
        # 获取下一个单词（用于显示下一个单词）
        if self.to_learn:
            self.next_word = self.to_learn[0]
        else:
            self.next_word = None
        
        return self.current_word
    
    def process_choice(self, word_obj, choice):
        """处理用户选择"""
        # 更新标签（转换为大写）
        word_obj.tag += choice.upper()
        
        # 处理用户选择
        if choice.upper() == 'H' and self.get_continuous_h_count(word_obj.tag) >= 6:
            # 连续6个H，移入已学习队列
            word_obj.learned = True
            self.learned.append(word_obj)
            return None, f"单词 '{word_obj.word}' 已移入已学习队列"
        elif len(word_obj.tag) == 1 and choice.upper() == 'H':
            # 第一次学习就选择H，直接移入已学习队列
            word_obj.learned = True
            self.learned.append(word_obj)
            return None, f"单词 '{word_obj.word}' 已移入已学习队列"
        else:
            # 计算插入位置
            if choice.upper() == 'L':
                insert_index = self.a - 1  # 转换为0-based索引
            elif choice.upper() == 'M':
                insert_index = self.b - 1
            else:  # choice == 'H'
                insert_pos = self.calculate_h_position(word_obj.tag)
                insert_index = insert_pos - 1  # 转换为0-based索引
            
            # 确保插入位置有效
            insert_index = max(0, min(insert_index, len(self.to_learn)))
            
            # 插入回待学习队列
            if insert_index >= len(self.to_learn):
                self.to_learn.append(word_obj)
            else:
                # 使用循环插入到指定位置
                temp = deque()
                for _ in range(insert_index):
                    if self.to_learn:
                        temp.append(self.to_learn.popleft())
                temp.append(word_obj)
                while self.to_learn:
                    temp.append(self.to_learn.popleft())
                self.to_learn = temp
            
            return word_obj, f"单词 '{word_obj.word}' 已插入待学习队列第 {insert_index + 1} 位"
    
    def undo_last_choice(self):
        """撤销上一次的选择"""
        if not self.previous_word:
            return None, "没有上一个单词可以撤销"
        
         # 清除上一个单词的最后一个标签字符
        if self.previous_word.tag:
            self.previous_word.tag = self.previous_word.tag[:-1]
        
        # 保存当前单词到队列中
        if self.current_word:
            self.to_learn.appendleft(self.current_word)
        
        # 恢复上一个单词的状态
        self.current_word = self.previous_word
        self.previous_word = None
        
        # 更新下一个单词
        if self.to_learn:
            self.next_word = self.to_learn[0]
        else:
            self.next_word = None
        
        return self.current_word, f"已返回到单词 '{self.current_word.word}'，标签已清除最后一次选择"
    
    def add_word(self, word, definition):
        """添加新单词到待学习队列并更新原始文件"""
        # 创建新单词对象
        new_word = Vocabulary(word, definition, tag="L", learned=False)
        
        # 计算插入位置（L选项的插入位置）
        insert_index = self.a - 1  # 转换为0-based索引
        
        # 确保插入位置有效
        insert_index = max(0, min(insert_index, len(self.to_learn)))
        
        # 插入到待学习队列
        if insert_index >= len(self.to_learn):
            self.to_learn.append(new_word)
        else:
            # 使用循环插入到指定位置
            temp = deque()
            for _ in range(insert_index):
                if self.to_learn:
                    temp.append(self.to_learn.popleft())
            temp.append(new_word)
            while self.to_learn:
                temp.append(self.to_learn.popleft())
            self.to_learn = temp
        
        # 更新原始文件
        success, file_message = self.update_source_file(word, definition, is_new=True)
        
        if success:
            return new_word, f"新单词 '{word}' 已添加到待学习队列第 {insert_index + 1} 位，并已保存到原始文件"
        else:
            return new_word, f"新单词 '{word}' 已添加到待学习队列第 {insert_index + 1} 位，但保存到原始文件失败: {file_message}"
    
    def update_source_file(self, word, definition, is_new=False, original_word=None, original_definition=None):
        """更新原始文件中的单词"""
        try:
            # 检查文件扩展名
            if self.filename.endswith('.xlsx') or self.filename.endswith('.xls'):
                # 读取Excel文件
                df = pd.read_excel(self.filename)
                
                if is_new:
                    # 添加新行
                    new_row = pd.DataFrame([[word, definition]], columns=df.columns)
                    df = pd.concat([df, new_row], ignore_index=True)
                else:
                    # 更新现有行
                    # 使用原始单词和释义来定位要修改的行
                    mask = (df.iloc[:, 0] == original_word)
                    if original_definition:
                        mask = mask & (df.iloc[:, 1] == original_definition)
                    
                    if mask.any():
                        # 更新找到的行
                        df.loc[mask, df.columns[0]] = word
                        df.loc[mask, df.columns[1]] = definition
                    else:
                        # 如果没有找到匹配的行，添加为新行
                        new_row = pd.DataFrame([[word, definition]], columns=df.columns)
                        df = pd.concat([df, new_row], ignore_index=True)
                
                # 写回文件
                df.to_excel(self.filename, index=False)
                return True, "Excel文件已更新"
            else:
                # 文本文件格式
                updated = False
                lines = []
                
                # 读取文件内容
                with open(self.filename, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.strip().split('\t')
                        if len(parts) >= 1:
                            current_word = parts[0]
                            current_definition = '\t'.join(parts[1:]) if len(parts) > 1 else ""
                            
                            # 检查是否是要更新的行
                            if not is_new and current_word == original_word and current_definition == original_definition:
                                # 更新这一行
                                lines.append(f"{word}\t{definition}\n")
                                updated = True
                            else:
                                # 保留原行
                                lines.append(line)
                
                # 如果是新单词，追加到文件末尾
                if is_new or not updated:
                    lines.append(f"{word}\t{definition}\n")
                
                # 写回文件
                with open(self.filename, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                
                return True, "文本文件已更新"
        except Exception as e:
            return False, str(e)
    
    def edit_word(self, word_obj, new_word, new_definition):
        """编辑单词"""
        # 保存原始值以便在文件中定位
        original_word = word_obj.original_word
        original_definition = word_obj.original_definition
        
        # 更新单词对象
        word_obj.word = new_word
        word_obj.definition = new_definition
        
        # 更新原始文件
        success, message = self.update_source_file(
            new_word, 
            new_definition, 
            is_new=False,
            original_word=original_word,
            original_definition=original_definition
        )
        
        # 更新原始值以便下次编辑
        word_obj.original_word = new_word
        word_obj.original_definition = new_definition
        
        return success, message
    
    def mark_as_learned(self, word_obj):
        """将单词标记为已学习"""
        word_obj.learned = True
        self.learned.append(word_obj)
        return word_obj, f"单词 '{word_obj.word}' 已直接移入已学习队列"

class VocabularyTrainerGUI:
    def __init__(self, root, trainer):
        self.root = root
        self.trainer = trainer
        self.current_word = None
        self.choice_made = False  # 标记用户是否已做出选择
        
        # 设置窗口标题和大小
        root.title("单词学习")
        root.geometry("700x650")  # 增加窗口高度以容纳参数设置
        root.configure(bg="#f0f0f0")  # 设置背景色
        root.resizable(True, True)
        
        # 绑定窗口关闭事件
        root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 参数设置区域
        self.params_frame = ttk.Frame(self.main_frame)
        self.params_frame.pack(fill=tk.X, pady=10)
        
        # a参数设置
        a_frame = ttk.Frame(self.params_frame)
        a_frame.pack(side=tk.LEFT, padx=10)
        
        a_label = ttk.Label(a_frame, text="L选项位置:", font=("Arial", 10))
        a_label.pack(side=tk.LEFT)
        
        self.a_var = tk.IntVar(value=self.trainer.a)
        self.a_spinbox = ttk.Spinbox(
            a_frame, 
            from_=1, 
            to=100, 
            width=5,
            textvariable=self.a_var,
            command=self.update_params
        )
        self.a_spinbox.pack(side=tk.LEFT, padx=5)
        self.a_spinbox.bind("<FocusOut>", lambda e: self.update_params())
        
        # b参数设置
        b_frame = ttk.Frame(self.params_frame)
        b_frame.pack(side=tk.LEFT, padx=10)
        
        b_label = ttk.Label(b_frame, text="M选项位置:", font=("Arial", 10))
        b_label.pack(side=tk.LEFT)
        
        self.b_var = tk.IntVar(value=self.trainer.b)
        self.b_spinbox = ttk.Spinbox(
            b_frame, 
            from_=1, 
            to=100, 
            width=5,
            textvariable=self.b_var,
            command=self.update_params
        )
        self.b_spinbox.pack(side=tk.LEFT, padx=5)
        self.b_spinbox.bind("<FocusOut>", lambda e: self.update_params())
        
        # 熟悉度说明标签
        legend_frame = ttk.Frame(self.params_frame)
        legend_frame.pack(side=tk.RIGHT, padx=10)
        
        self.legend_label = ttk.Label(
            legend_frame, 
            text="L-陌生 | M-模糊 | H-熟悉", 
            font=("Arial", 10, "bold"),
            foreground="#3498db"  # 蓝色
        )
        self.legend_label.pack(side=tk.RIGHT)
        
        # 单词显示区域
        self.word_frame = ttk.Frame(self.main_frame)
        self.word_frame.pack(fill=tk.X, pady=10)
        
        self.word_label = ttk.Label(
            self.word_frame, 
            text="", 
            font=("Arial", 36, "bold"),
            anchor=tk.CENTER,
            foreground="#3498db"  # 蓝色
        )
        self.word_label.pack(fill=tk.X)
        
        # 释义显示区域 - 简洁版
        self.definition_frame = ttk.Frame(self.main_frame)
        self.definition_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 添加滚动条
        self.definition_scrollbar = ttk.Scrollbar(self.definition_frame)
        self.definition_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.definition_text = tk.Text(
            self.definition_frame, 
            wrap=tk.WORD,
            font=("Arial", 18),
            yscrollcommand=self.definition_scrollbar.set,
            height=6,
            padx=15,
            pady=15,
            bg="#f8f9fa",  # 浅灰色背景
            relief=tk.FLAT,
            borderwidth=0
        )
        self.definition_text.tag_configure("center", justify='center')
        self.definition_text.pack(fill=tk.BOTH, expand=True)
        self.definition_text.config(state=tk.DISABLED)  # 初始为只读
        
        self.definition_scrollbar.config(command=self.definition_text.yview)
        
        # 标签显示区域
        self.tag_frame = ttk.Frame(self.main_frame)
        self.tag_frame.pack(fill=tk.X, pady=5)
        
        self.tag_label = ttk.Label(
            self.tag_frame, 
            text="", 
            font=("Arial", 14),
            anchor=tk.CENTER,
            foreground="#7f8c8d"  # 灰色
        )
        self.tag_label.pack(fill=tk.X)
        
        # 状态显示区域
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.pack(fill=tk.X, pady=5)
        
        self.status_label = ttk.Label(
            self.status_frame, 
            text="", 
            font=("Arial", 12),
            anchor=tk.CENTER,
            foreground="#3498db"  # 蓝色
        )
        self.status_label.pack(fill=tk.X)
        
        # 选择按钮区域 - 居中显示
        self.choice_frame = ttk.Frame(self.main_frame)
        self.choice_frame.pack(fill=tk.X, pady=20)
        
        # 创建内部框架用于居中按钮
        self.button_container = ttk.Frame(self.choice_frame)
        self.button_container.pack(expand=True)
        
        # 创建选择按钮 - 水平排列
        # 使用tk.Button实现纯色按钮
        self.low_button = tk.Button(
            self.button_container, 
            text="陌生 (L)", 
            command=lambda: self.process_choice('L'),
            bg="#e74c3c",  # 红色背景
            fg="white",     # 白色文字
            font=("Arial", 14, "bold"),
            width=10,
            height=2,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#c0392b"  # 激活状态颜色
        )
        self.low_button.grid(row=0, column=1, padx=15, pady=10)
        
        self.medium_button = tk.Button(
            self.button_container, 
            text="模糊 (M)", 
            command=lambda: self.process_choice('M'),
            bg="#f39c12",  # 黄色背景
            fg="white",     # 白色文字
            font=("Arial", 14, "bold"),
            width=10,
            height=2,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#d35400"  # 激活状态颜色
        )
        self.medium_button.grid(row=0, column=2, padx=15, pady=10)
        
        self.high_button = tk.Button(
            self.button_container, 
            text="熟悉 (H)", 
            command=lambda: self.process_choice('H'),
            bg="#2ecc71",  # 绿色背景
            fg="white",     # 白色文字
            font=("Arial", 14, "bold"),
            width=10,
            height=2,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#27ae60"  # 激活状态颜色
        )
        self.high_button.grid(row=0, column=3, padx=15, pady=10)

        # 在选择按钮区域添加新按钮
        self.master_button = tk.Button(
            self.button_container, 
            text="已掌握 (✓)", 
            command=self.mark_as_learned,
            bg="#95a5a6",  # 灰色背景
            fg="white",     # 白色文字
            font=("Arial", 14, "bold"),
            width=10,
            height=2,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#7f8c8d"  # 激活状态颜色
        )
        self.master_button.grid(row=0, column=4, padx=15, pady=10)  # 放在H按钮右侧
        
        # 在左侧添加透明占位按钮
        self.transparent_button = tk.Button(
            self.button_container, 
            text="", 
            command=lambda: None,  # 空命令
            bg=self.root.cget('bg'),  # 使用主窗口背景色
            fg=self.root.cget('bg'),  # 文字颜色与背景相同
            font=("Arial", 14),
            width=10,
            height=2,
            relief=tk.FLAT,
            borderwidth=0,
            state=tk.DISABLED  # 禁用状态
        )
        self.transparent_button.grid(row=0, column=0, padx=15, pady=10)

        # 添加"下一个单词"按钮 - 在三个按钮下方
        self.next_button = tk.Button(
            self.button_container, 
            text="下一个单词", 
            command=self.show_next_word,
            bg="#3498db",  # 蓝色背景
            fg="white",    # 白色文字
            font=("Arial", 14, "bold"),
            width=15,
            height=2,
            relief=tk.FLAT,
            borderwidth=0,
            state=tk.DISABLED,
            activebackground="#2980b9"  # 激活状态颜色
        )
        self.next_button.grid(row=1, column=1, columnspan=3, pady=15)
        
        # 添加"上一个单词"按钮 - 在三个按钮下方
        self.prev_button = tk.Button(
            self.button_container, 
            text="上一个单词", 
            command=self.show_previous_word,
            bg="#9b59b6",  # 紫色背景
            fg="white",    # 白色文字
            font=("Arial", 14, "bold"),
            width=15,
            height=2,
            relief=tk.FLAT,
            borderwidth=0,
            state=tk.DISABLED,
            activebackground="#8e44ad"  # 激活状态颜色
        )
        self.prev_button.grid(row=2, column=1, columnspan=3, pady=15)
        
        # 底部按钮区域 - 右下角
        self.bottom_frame = ttk.Frame(self.main_frame)
        self.bottom_frame.pack(fill=tk.X, pady=20)
        
        # 在右下角添加重置按钮
        self.reset_button = tk.Button(
            self.bottom_frame, 
            text="重置进度", 
            command=self.reset_progress,
            bg="#95a5a6",  # 灰色背景
            fg="white",    # 白色文字
            font=("Arial", 12, "bold"),
            width=12,
            height=1,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#7f8c8d"  # 激活状态颜色
        )
        self.reset_button.pack(side=tk.RIGHT, padx=10)
        
        # 添加单词按钮
        self.add_word_button = tk.Button(
            self.bottom_frame, 
            text="添加单词", 
            command=self.add_word,
            bg="#9b59b6",  # 紫色背景
            fg="white",    # 白色文字
            font=("Arial", 12, "bold"),
            width=10,
            height=1,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#8e44ad"  # 激活状态颜色
        )
        self.add_word_button.pack(side=tk.RIGHT, padx=10)
        
        # 编辑单词按钮
        self.edit_word_button = tk.Button(
            self.bottom_frame, 
            text="编辑单词", 
            command=self.edit_word,
            bg="#3498db",  # 蓝色背景
            fg="white",    # 白色文字
            font=("Arial", 12, "bold"),
            width=10,
            height=1,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#2980b9"  # 激活状态颜色
        )
        self.edit_word_button.pack(side=tk.RIGHT, padx=10)
        
        # 退出按钮 - 放在右下角
        self.exit_button = tk.Button(
            self.bottom_frame, 
            text="退出", 
            command=self.exit_program,
            bg="#95a5a6",  # 灰色背景
            fg="white",    # 白色文字
            font=("Arial", 12, "bold"),
            width=8,
            height=1,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#7f8c8d"  # 激活状态颜色
        )
        self.exit_button.pack(side=tk.RIGHT, padx=10)
        
        # 开始显示第一个单词
        self.show_next_word()
    
    def update_params(self):
        """更新a和b参数"""
        try:
            a_val = int(self.a_var.get())
            b_val = int(self.b_var.get())
            
            if a_val < 1 or b_val < 1:
                messagebox.showerror("错误", "参数值必须大于0")
                return
            
            self.trainer.a = a_val
            self.trainer.b = b_val
            
            # 保存进度
            self.trainer.save_progress()
            
            self.status_label.config(text=f"参数已更新: L位置={a_val}, M位置={b_val}")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的整数")

    def mark_as_learned(self):
        """将当前单词标记为已掌握"""
        if not self.current_word:
            return
        
        # 标记为已学习
        word_obj, message = self.trainer.mark_as_learned(self.current_word)
        
        # 显示释义
        self.definition_text.config(state=tk.NORMAL)
        self.definition_text.delete(1.0, tk.END)
        self.definition_text.insert(tk.END, self.current_word.definition, "center")
        self.definition_text.config(state=tk.DISABLED)
        
        # 更新标签显示
        self.tag_label.config(text=f"标签: {self.current_word.tag}✓")
        
        # 显示状态信息
        self.status_label.config(text=message)
        
        # 更新按钮状态
        self.low_button.config(state=tk.DISABLED)    # 禁用选择按钮
        self.medium_button.config(state=tk.DISABLED)
        self.high_button.config(state=tk.DISABLED)
        self.master_button.config(state=tk.DISABLED)  # 禁用已掌握按钮
        self.next_button.config(state=tk.NORMAL)      # 启用"下一个"按钮
        self.prev_button.config(state=tk.DISABLED)   # 禁用"上一个"按钮
        
        # 保存进度
        self.trainer.save_progress()
    
    def show_next_word(self):
        """显示下一个单词"""
        # 如果当前有单词且用户已经做出了选择，处理当前单词
        if self.current_word and self.choice_made:
            # 处理用户选择
            word_obj, message = self.trainer.process_choice(self.current_word, self.current_choice)
            self.status_label.config(text=message)
            self.choice_made = False  # 重置选择标记
        
        # 获取下一个单词
        self.current_word = self.trainer.get_next_word()
        
        if not self.current_word:
            self.show_completion()
            return
        
        self.word_label.config(text=self.current_word.word)
        
        # 更新释义显示 - 初始时不显示释义
        self.definition_text.config(state=tk.NORMAL)
        self.definition_text.delete(1.0, tk.END)
        self.definition_text.config(state=tk.DISABLED)
        
        self.tag_label.config(text=f"标签: {self.current_word.tag}")
        
        # 更新按钮状态
        self.next_button.config(state=tk.DISABLED)  # 禁用"下一个"按钮
        self.prev_button.config(state=tk.NORMAL if self.trainer.previous_word else tk.DISABLED)  # 根据是否有上一个单词启用/禁用
        self.low_button.config(state=tk.NORMAL)     # 启用选择按钮
        self.medium_button.config(state=tk.NORMAL)
        self.high_button.config(state=tk.NORMAL)
        self.master_button.config(state=tk.NORMAL)  # 启用已掌握按钮
        self.edit_word_button.config(state=tk.NORMAL)  # 启用编辑按钮
        
        # 更新状态
        self.update_status()
        
        # 保存进度
        self.trainer.save_progress()
    
    def show_previous_word(self):
        """显示上一个单词"""
        # 撤销上一个单词的选择
        prev_word, message = self.trainer.undo_last_choice()
        
        if not prev_word:
            self.status_label.config(text=message)
            return
        
        # 设置当前单词为上一个单词
        self.current_word = prev_word
        self.word_label.config(text=self.current_word.word)
        
        # 显示释义
        self.definition_text.config(state=tk.NORMAL)
        self.definition_text.delete(1.0, tk.END)
        self.definition_text.insert(tk.END, self.current_word.definition,"center")
        self.definition_text.config(state=tk.DISABLED)
        
        self.tag_label.config(text=f"标签: {self.current_word.tag}")
        
        # 更新状态信息
        self.status_label.config(text=message)
        
        # 更新按钮状态
        self.next_button.config(state=tk.DISABLED)  # 禁用"下一个"按钮
        self.prev_button.config(state=tk.DISABLED)  # 禁用"上一个"按钮（只能回退一步）
        self.low_button.config(state=tk.NORMAL)     # 启用选择按钮
        self.medium_button.config(state=tk.NORMAL)
        self.high_button.config(state=tk.NORMAL)
        self.master_button.config(state=tk.NORMAL)  # 启用已掌握按钮
        self.edit_word_button.config(state=tk.NORMAL)  # 启用编辑按钮
        
        # 标记用户尚未做出选择
        self.choice_made = False
        
        # 更新状态
        self.update_status()
        
        # 保存进度
        self.trainer.save_progress()
    
    def update_status(self):
        """更新状态信息"""
        to_learn_count = len(self.trainer.to_learn)
        learned_count = len(self.trainer.learned)
        self.status_label.config(
            text=f"待学习: {to_learn_count} | 已学习: {learned_count} | L位置={self.trainer.a}, M位置={self.trainer.b}"
        )
    
    def process_choice(self, choice):
        """处理用户选择"""
        if not self.current_word:
            return
        
        # 显示释义
        self.definition_text.config(state=tk.NORMAL)
        self.definition_text.delete(1.0, tk.END)
        self.definition_text.insert(tk.END, self.current_word.definition,"center")
        self.definition_text.config(state=tk.DISABLED)
        
        # 保存用户选择
        self.current_choice = choice
        self.choice_made = True
        
        # 更新标签显示
        self.tag_label.config(text=f"标签: {self.current_word.tag}{choice}")
        
        # 计算并显示单词将进入的位置
        position_info = self.calculate_position_info(choice)
        
        # 显示状态信息
        choice_text = "陌生" if choice == 'L' else "模糊" if choice == 'M' else "熟悉"
        self.status_label.config(text=f"已选择: {choice_text} - {position_info}")
        
        # 更新按钮状态
        self.low_button.config(state=tk.DISABLED)    # 禁用选择按钮
        self.medium_button.config(state=tk.DISABLED)
        self.high_button.config(state=tk.DISABLED)
        self.master_button.config(state=tk.DISABLED)  #禁用已掌握按钮
        self.next_button.config(state=tk.NORMAL)      # 启用"下一个"按钮
        self.prev_button.config(state=tk.DISABLED)   # 禁用"上一个"按钮（因为已经做出选择）
        self.edit_word_button.config(state=tk.NORMAL)  # 禁用编辑按钮（因为已经做出选择）改成启用
        
        # 保存进度
        self.trainer.save_progress()
    
    def calculate_position_info(self, choice):
        """计算并返回单词将进入的位置信息"""
        temp_tag = self.current_word.tag + choice
        
        # 检查是否会移入已学习队列
        if choice == 'H' and self.trainer.get_continuous_h_count(temp_tag) >= 6:
            return "单词将移入已学习队列"
        elif len(temp_tag) == 1 and choice == 'H':
            return "单词将移入已学习队列"
        else:
            # 计算插入位置
            if choice == 'L':
                insert_index = self.trainer.a - 1  # 转换为0-based索引
            elif choice == 'M':
                insert_index = self.trainer.b - 1
            else:  # choice == 'H'
                insert_pos = self.trainer.calculate_h_position(temp_tag)
                insert_index = insert_pos - 1  # 转换为0-based索引
            
            # 确保插入位置有效
            insert_index = max(0, min(insert_index, len(self.trainer.to_learn)))
            
            return f"单词将插入待学习队列第 {insert_index + 1} 位"
    
    def show_completion(self):
        """显示学习完成信息"""
        self.word_label.config(text="学习完成！")
        
        # 更新释义显示
        self.definition_text.config(state=tk.NORMAL)
        self.definition_text.delete(1.0, tk.END)
        self.definition_text.config(state=tk.DISABLED)
        
        self.tag_label.config(text="")
        
        to_learn_count = len(self.trainer.to_learn)
        learned_count = len(self.trainer.learned)
        self.status_label.config(
            text=f"所有单词学习完成！待学习: {to_learn_count} | 已学习: {learned_count} | L位置={self.trainer.a}, M位置={self.trainer.b}"
        )
        
        # 禁用所有按钮
        self.low_button.config(state=tk.DISABLED)
        self.medium_button.config(state=tk.DISABLED)
        self.high_button.config(state=tk.DISABLED)
        self.master_button.config(state=tk.DISABLED)  # 禁用已掌握按钮
        self.next_button.config(state=tk.DISABLED)
        self.prev_button.config(state=tk.DISABLED)
        self.edit_word_button.config(state=tk.DISABLED)
        
        # 保存进度
        self.trainer.save_progress()
    
    def reset_progress(self):
        """重置学习进度"""
        if messagebox.askyesno("确认", "确定要重置学习进度吗？这将删除所有保存的数据并重新开始。"):
            # 删除进度文件
            if os.path.exists(self.trainer.progress_file):
                try:
                    os.remove(self.trainer.progress_file)
                except Exception as e:
                    messagebox.showerror("错误", f"删除进度文件失败: {e}")
                    return
            
            # 重新加载文件
            filename = self.trainer.filename
            self.trainer = VocabularyTrainer(a=10, b=15)
            self.trainer.load_from_file(filename)
            
            # 更新参数显示
            self.a_var.set(self.trainer.a)
            self.b_var.set(self.trainer.b)
            
            # 重置界面
            self.current_word = None
            self.choice_made = False
            self.show_next_word()
    
    def add_word(self):
        """添加新单词"""
        # 创建输入对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("添加新单词")
        dialog.geometry("500x300")
        dialog.resizable(False, False)
        dialog.transient(self.root)  # 设置为主窗口的子窗口
        dialog.grab_set()  # 模态对话框
        
        # 单词输入框
        word_frame = ttk.Frame(dialog, padding=10)
        word_frame.pack(fill=tk.X, pady=5)
        
        word_label = ttk.Label(word_frame, text="单词:", font=("Arial", 12))
        word_label.pack(side=tk.LEFT, padx=5)
        
        word_entry = ttk.Entry(word_frame, font=("Arial", 12), width=40)
        word_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        word_entry.focus_set()  # 设置焦点
        
        # 释义输入框
        definition_frame = ttk.Frame(dialog, padding=10)
        definition_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        definition_label = ttk.Label(definition_frame, text="释义:", font=("Arial", 12))
        definition_label.pack(anchor=tk.NW, padx=5)
        
        definition_text = tk.Text(definition_frame, font=("Arial", 12), height=6, wrap=tk.WORD)
        definition_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 按钮区域
        button_frame = ttk.Frame(dialog, padding=10)
        button_frame.pack(fill=tk.X, pady=5)
        
        def on_submit():
            """提交新单词"""
            word = word_entry.get().strip()
            definition = definition_text.get("1.0", tk.END).strip()
            
            if not word:
                messagebox.showerror("错误", "单词不能为空")
                return
            
            # 添加新单词
            new_word, message = self.trainer.add_word(word, definition)
            
            # 显示成功消息
            messagebox.showinfo("成功", message)
            
            # 更新状态
            self.update_status()
            
            # 保存进度
            self.trainer.save_progress()
            
            # 如果当前没有单词在显示，立即显示新单词
            if not self.trainer.to_learn or self.trainer.to_learn[0] == new_word:
                self.current_word = new_word
                self.word_label.config(text=new_word.word)
                # 新单词显示时不显示释义
                self.definition_text.config(state=tk.NORMAL)
                self.definition_text.delete(1.0, tk.END)
                self.definition_text.config(state=tk.DISABLED)
                self.tag_label.config(text=f"标签: {new_word.tag}")
            
            # 关闭对话框
            dialog.destroy()
        
        submit_button = tk.Button(
            button_frame, 
            text="添加", 
            command=on_submit,
            bg="#2ecc71",  # 绿色背景
            fg="white",    # 白色文字
            font=("Arial", 12, "bold"),
            width=10,
            height=1,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#27ae60"  # 激活状态颜色
        )
        submit_button.pack(side=tk.RIGHT, padx=10)
        
        cancel_button = tk.Button(
            button_frame, 
            text="取消", 
            command=dialog.destroy,
            bg="#95a5a6",  # 灰色背景
            fg="white",    # 白色文字
            font=("Arial", 12, "bold"),
            width=10,
            height=1,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#7f8c8d"  # 激活状态颜色
        )
        cancel_button.pack(side=tk.RIGHT, padx=10)
    
    def edit_word(self):
        """编辑当前单词"""
        if not self.current_word:
            messagebox.showinfo("提示", "没有当前单词可编辑")
            return
        
        # 创建编辑对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑单词")
        dialog.geometry("500x300")
        dialog.resizable(False, False)
        dialog.transient(self.root)  # 设置为主窗口的子窗口
        dialog.grab_set()  # 模态对话框
        
        # 单词输入框
        word_frame = ttk.Frame(dialog, padding=10)
        word_frame.pack(fill=tk.X, pady=5)
        
        word_label = ttk.Label(word_frame, text="单词:", font=("Arial", 12))
        word_label.pack(side=tk.LEFT, padx=5)
        
        word_entry = ttk.Entry(word_frame, font=("Arial", 12), width=40)
        word_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        word_entry.insert(0, self.current_word.word)
        word_entry.focus_set()  # 设置焦点
        
        # 释义输入框
        definition_frame = ttk.Frame(dialog, padding=10)
        definition_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        definition_label = ttk.Label(definition_frame, text="释义:", font=("Arial", 12))
        definition_label.pack(anchor=tk.NW, padx=5)
        
        definition_text = tk.Text(definition_frame, font=("Arial", 12), height=6, wrap=tk.WORD)
        definition_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        definition_text.insert(tk.END, self.current_word.definition)
        
        # 按钮区域
        button_frame = ttk.Frame(dialog, padding=10)
        button_frame.pack(fill=tk.X, pady=5)
        
        def on_submit():
            """提交编辑"""
            new_word = word_entry.get().strip()
            new_definition = definition_text.get("1.0", tk.END).strip()
            
            if not new_word:
                messagebox.showerror("错误", "单词不能为空")
                return
            
            # 编辑单词
            success, message = self.trainer.edit_word(self.current_word, new_word, new_definition)
            
            if success:
                # 更新界面显示
                self.word_label.config(text=new_word)
                self.definition_text.config(state=tk.NORMAL)
                self.definition_text.delete(1.0, tk.END)
                self.definition_text.insert(tk.END, new_definition, "center")
                self.definition_text.config(state=tk.DISABLED)
                
                # 显示成功消息
                messagebox.showinfo("成功", message)
                
                # 更新状态
                self.update_status()
                
                # 保存进度
                self.trainer.save_progress()
            else:
                messagebox.showerror("错误", f"编辑单词失败: {message}")
            
            # 关闭对话框
            dialog.destroy()
        
        submit_button = tk.Button(
            button_frame, 
            text="保存", 
            command=on_submit,
            bg="#2ecc71",  # 绿色背景
            fg="white",    # 白色文字
            font=("Arial", 12, "bold"),
            width=10,
            height=1,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#27ae60"  # 激活状态颜色
        )
        submit_button.pack(side=tk.RIGHT, padx=10)
        
        cancel_button = tk.Button(
            button_frame, 
            text="取消", 
            command=dialog.destroy,
            bg="#95a5a6",  # 灰色背景
            fg="white",    # 白色文字
            font=("Arial", 12, "bold"),
            width=10,
            height=1,
            relief=tk.FLAT,
            borderwidth=0,
            activebackground="#7f8c8d"  # 激活状态颜色
        )
        cancel_button.pack(side=tk.RIGHT, padx=10)
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 保存进度
        self.trainer.save_progress()
        self.root.destroy()
    
    def exit_program(self):
        """退出程序"""
        self.on_closing()

# 修改主程序部分
if __name__ == "__main__":
    # 创建主窗口但不立即显示
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    
    # 弹出文件选择对话框
    filename = filedialog.askopenfilename(
        title="选择单词文件",
        filetypes=[("Excel文件", "*.xlsx *.xls"), ("文本文件", "*.txt")]
    )
    
    if not filename:
        print("未选择文件，程序退出")
        sys.exit(0)
    
    # 创建训练器并加载文件
    trainer = VocabularyTrainer(a=10, b=15)
    trainer.load_from_file(filename)
    
    # 销毁临时隐藏的根窗口
    root.destroy()
    
    # 创建新的主GUI窗口
    root = tk.Tk()
    app = VocabularyTrainerGUI(root, trainer)
    root.mainloop()