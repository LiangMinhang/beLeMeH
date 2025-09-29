# 全局字典，用于存储每个用户的训练器状态
user_trainers = {}

import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
import json
import hashlib
from collections import deque
import uuid
from flask import jsonify

# 初始化Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # 替换为随机字符串
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'data/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'xlsx', 'xls'}

# 确保上传文件夹存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 初始化扩展
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# 用户模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    vocab_files = db.relationship('VocabFile', backref='user', lazy=True)

# 词汇文件模型
class VocabFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    filepath = db.Column(db.String(300))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    progress_data = db.Column(db.Text)  # 存储JSON格式的进度数据

# 用户加载器
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 词汇类（从原代码复制）
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
            'learned': self.learned,
            'original_word': self.original_word,
            'original_definition': self.original_definition
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建单词对象"""
        word_obj = cls(data['word'], data['definition'], data['tag'], data['learned'])
        word_obj.original_word = data.get('original_word', data['word'])
        word_obj.original_definition = data.get('original_definition', data['definition'])
        return word_obj
    
# 保存训练器进度到数据库的辅助函数
def save_trainer_progress(user_id, file_id):
    """保存训练器进度到数据库"""
    user_trainer = user_trainers.get(user_id)
    if not user_trainer:
        return False
    
    trainer = user_trainer['trainer']
    file = VocabFile.query.get(file_id)
    
    if not file:
        return False
    
    try:
        # 保存进度到数据库
        file.progress_data = trainer.save_progress()
        db.session.commit()
        return True
    except Exception as e:
        print(f"保存进度失败: {e}")
        db.session.rollback()
        return False

# VocabularyTrainer类（完整版本）
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
    
    def save_progress(self):
        """将当前进度转换为可序列化的字典"""
        progress_data = {
            'a': self.a,
            'b': self.b,
            'to_learn': [word.to_dict() for word in self.to_learn],
            'learned': [word.to_dict() for word in self.learned],
            'previous_word': self.previous_word.to_dict() if self.previous_word else None,
            'current_word': self.current_word.to_dict() if self.current_word else None,
            'next_word': self.next_word.to_dict() if self.next_word else None,
            'filename': self.filename
        }
        return json.dumps(progress_data, ensure_ascii=False)
    

    def load_progress(self, progress_json):
        """从JSON字符串加载进度"""
        if not progress_json:
            return False
        
        try:
            progress_data = json.loads(progress_json)
            
            self.a = progress_data.get('a', 5)
            self.b = progress_data.get('b', 10)
            self.filename = progress_data.get('filename', '')
            
            # 恢复待学习队列
            self.to_learn = deque()
            for word_dict in progress_data.get('to_learn', []):
                self.to_learn.append(Vocabulary.from_dict(word_dict))
            
            # 恢复已学习队列
            self.learned = []
            for word_dict in progress_data.get('learned', []):
                self.learned.append(Vocabulary.from_dict(word_dict))
            
            # 恢复单词状态
            prev_word = progress_data.get('previous_word')
            self.previous_word = Vocabulary.from_dict(prev_word) if prev_word else None
            
            curr_word = progress_data.get('current_word')
            self.current_word = Vocabulary.from_dict(curr_word) if curr_word else None
            
            next_word = progress_data.get('next_word')
            self.next_word = Vocabulary.from_dict(next_word) if next_word else None
            
            return True
        except Exception as e:
            print(f"加载进度失败: {e}")
            return False

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
            return True, "文件加载成功"
        except FileNotFoundError:
            return False, f"文件 {filename} 未找到"
        except Exception as e:
            return False, f"读取文件时出错: {e}"
    
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
    
    def can_undo_last_choice(self):
        """检查是否可以撤销上一次选择"""
        return self.previous_word is not None
    
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
        
        return new_word, f"新单词 '{word}' 已添加到待学习队列第 {insert_index + 1} 位"
    
    def mark_as_learned(self, word_obj):
        """将单词标记为已学习"""
        word_obj.learned = True
        self.learned.append(word_obj)
        return word_obj, f"单词 '{word_obj.word}' 已直接移入已学习队列"
        
    # 其他方法保持不变，从原代码复制...
    # 包括：get_continuous_h_count, calculate_h_position, get_next_word, 
    # process_choice, undo_last_choice, add_word, update_source_file, 
    # edit_word, mark_as_learned

# 辅助函数：检查文件扩展名
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# 路由：首页
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('trainer'))
    return render_template('index.html')

# 路由：登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('trainer'))
        else:
            flash('用户名或密码错误')
    
    return render_template('login.html')

# 路由：注册
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 检查用户名是否已存在
        user = User.query.filter_by(username=username).first()
        if user:
            flash('用户名已存在')
            return redirect(url_for('register'))
        
        # 创建新用户
        new_user = User(
            username=username,
            password=generate_password_hash(password, method='sha256')
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('注册成功，请登录')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# 路由：登出
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# 路由：文件上传（修改为支持多文件）
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        # 检查是否有文件上传
        if 'file' not in request.files:
            flash('没有选择文件')
            return redirect(request.url)
        
        file = request.files['file']
        
        # 检查文件名
        if file.filename == '':
            flash('没有选择文件')
            return redirect(request.url)
        
        # 检查文件扩展名
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            # 保存文件信息到数据库
            vocab_file = VocabFile(
                filename=filename,
                filepath=filepath,
                user_id=current_user.id,
                progress_data=None,  # 初始化为空
            )
            db.session.add(vocab_file)
            db.session.commit()
            
            flash('文件上传成功')
            return redirect(url_for('file_manager'))
        else:
            flash('不支持的文件类型')
    
    return render_template('upload.html')

# 新增路由：文件管理
@app.route('/file_manager')
@login_required
def file_manager():
    # 获取用户上传的所有文件
    files = VocabFile.query.filter_by(user_id=current_user.id).all()
    
    return render_template('file_manager.html', files=files)

# 路由：选择文件
@app.route('/select_file/<int:file_id>')
@login_required
def select_file(file_id):
    # 获取文件
    file = VocabFile.query.get(file_id)
    
    if not file or file.user_id != current_user.id:
        flash('文件不存在或无权访问')
        return redirect(url_for('file_manager'))
    
    # 初始化训练器
    trainer = VocabularyTrainer(a=10, b=15)
    
    # 尝试从数据库加载进度
    if file.progress_data:
        success = trainer.load_progress(file.progress_data)
        if success:
            # 进度加载成功
            flash(f'已恢复文件 "{file.filename}" 的学习进度')
        else:
            # 进度加载失败，从文件重新加载
            success, message = trainer.load_from_file(file.filepath)
            if not success:
                flash(message)
                return redirect(url_for('file_manager'))
            flash(f'已重新加载文件 "{file.filename}"')
    else:
        # 没有保存的进度，从文件加载
        success, message = trainer.load_from_file(file.filepath)
        if not success:
            flash(message)
            return redirect(url_for('file_manager'))
        flash(f'已加载文件 "{file.filename}"')
    
    # 保存训练器状态
    user_trainers[current_user.id] = {
        'trainer': trainer,
        'file_id': file_id
    }
    
    # 如果没有当前单词，获取下一个单词
    if not trainer.current_word:
        word = trainer.get_next_word()
    else:
        word = trainer.current_word
    
    if word is None:
        return render_template('trainer.html', 
                             word=Vocabulary("学习完成", "所有单词已学习完毕", "", True), 
                             trainer=trainer,
                             current_file=file)
    
    return render_template('trainer.html', word=word, trainer=trainer, current_file=file)

# 路由：删除文件
@app.route('/delete_file/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    # 获取文件
    file = VocabFile.query.get(file_id)
    
    if not file or file.user_id != current_user.id:
        return jsonify({'success': False, 'message': '文件不存在或无权访问'})
    
    try:
        # 删除物理文件
        if os.path.exists(file.filepath):
            os.remove(file.filepath)
        
        # 删除数据库记录
        db.session.delete(file)
        db.session.commit()
        
        # 如果删除的是当前活动文件，清除训练器状态
        if user_trainers.get(current_user.id) and user_trainers[current_user.id]['file_id'] == file_id:
            del user_trainers[current_user.id]
        
        return jsonify({'success': True, 'message': '文件已删除'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除文件失败: {str(e)}'})

# 路由：学习界面（修改为使用全局训练器状态）
@app.route('/trainer')
@login_required
def trainer():
    # 检查是否有活动训练器
    user_trainer = user_trainers.get(current_user.id)
    
    if not user_trainer:
        return redirect(url_for('file_manager'))
    
    trainer = user_trainer['trainer']
    file_id = user_trainer['file_id']
    
    # 获取文件
    file = VocabFile.query.get(file_id)
    
    # 获取下一个单词
    word = trainer.get_next_word()
    
    if word is None:
        return render_template('trainer.html', 
                             word=Vocabulary("学习完成", "所有单词已学习完毕", "", True), 
                             trainer=trainer,
                             current_file=file)
    
    return render_template('trainer.html', word=word, trainer=trainer, current_file=file)

# 路由：处理选择（修改为使用全局训练器状态）
@app.route('/process_choice', methods=['POST'])
@login_required
def process_choice():
    # 获取用户选择
    choice = request.json.get('choice')
    
    # 从全局字典获取训练器状态
    user_trainer = user_trainers.get(current_user.id)
    if not user_trainer:
        return jsonify({'success': False, 'message': '训练器未初始化'})
    
    trainer = user_trainer['trainer']
    file_id = user_trainer['file_id']
    
    # 获取当前单词
    word = trainer.current_word
    if not word:
        return jsonify({'success': False, 'message': '没有当前单词'})
    
    # 处理选择
    _, message = trainer.process_choice(word, choice)
    
    # 保存训练器状态
    user_trainers[current_user.id] = user_trainer
    
    # 处理选择后保存进度
    save_trainer_progress(current_user.id, file_id)

    return jsonify({
        'success': True,
        'message': message,
        'word': {
            'word': word.word,
            'definition': word.definition,
            'tag': word.tag
        },
        'status': f"待学习: {len(trainer.to_learn)} | 已学习: {len(trainer.learned)} | L位置={trainer.a}, M位置={trainer.b}",
        'can_undo': trainer.can_undo_last_choice()
    })

# 路由：获取下一个单词（修改为使用全局训练器状态）
@app.route('/next_word')
@login_required
def next_word():
    # 从全局字典获取训练器状态
    user_trainer = user_trainers.get(current_user.id)
    if not user_trainer:
        return jsonify({'success': False, 'message': '训练器未初始化'})
    
    trainer = user_trainer['trainer']
    file_id = user_trainer['file_id']
    
    # 获取下一个单词
    word = trainer.get_next_word()
    
    # 保存训练器状态
    user_trainers[current_user.id] = user_trainer
    
    # 获取下一个单词后保存进度
    save_trainer_progress(current_user.id, file_id)
    
    if not word:
        return jsonify({
            'success': True,
            'word': {
                'word': "学习完成",
                'definition': "所有单词已学习完毕",
                'tag': "",
                'learned': True
            },
            'status': f"待学习: {len(trainer.to_learn)} | 已学习: {len(trainer.learned)} | L位置={trainer.a}, M位置={trainer.b}"
        })
    
    return jsonify({
        'success': True,
        'word': {
            'word': word.word,
            'definition': word.definition,
            'tag': word.tag
        },
        'status': f"待学习: {len(trainer.to_learn)} | 已学习: {len(trainer.learned)} | L位置={trainer.a}, M位置={trainer.b}",
        'can_undo': trainer.can_undo_last_choice()
    })

# 路由：获取上一个单词（修改为使用全局训练器状态）
@app.route('/prev_word')
@login_required
def prev_word():
    # 从全局字典获取训练器状态
    user_trainer = user_trainers.get(current_user.id)
    if not user_trainer:
        return jsonify({'success': False, 'message': '训练器未初始化'})
    
    trainer = user_trainer['trainer']
    file_id = user_trainer['file_id']
    
    # 撤销上一次选择
    word, message = trainer.undo_last_choice()
    if not word:
        return jsonify({'success': False, 'message': message})
    
    # 保存训练器状态
    user_trainers[current_user.id] = user_trainer
    
    # 撤销操作后保存进度
    save_trainer_progress(current_user.id, file_id)
    
    return jsonify({
        'success': True,
        'word': {
            'word': word.word,
            'definition': word.definition,
            'tag': word.tag
        },
        'message': message,
        'status': f"待学习: {len(trainer.to_learn)} | 已学习: {len(trainer.learned)} | L位置={trainer.a}, M位置={trainer.b}",
        'can_undo': trainer.can_undo_last_choice()
    })

# 路由：标记为已掌握（修改为使用全局训练器状态）
@app.route('/mark_learned', methods=['POST'])
@login_required
def mark_learned():
    # 从全局字典获取训练器状态
    user_trainer = user_trainers.get(current_user.id)
    if not user_trainer:
        return jsonify({'success': False, 'message': '训练器未初始化'})
    
    trainer = user_trainer['trainer']
    file_id = user_trainer['file_id']
    
    # 获取当前单词
    word = trainer.current_word
    if not word:
        return jsonify({'success': False, 'message': '没有当前单词'})
    
    # 标记为已掌握
    _, message = trainer.mark_as_learned(word)
    
    # 保存训练器状态
    user_trainers[current_user.id] = user_trainer
    
    # 标记为已掌握后保存进度
    save_trainer_progress(current_user.id, file_id)
    
    return jsonify({
        'success': True,
        'message': message,
        'word': {
            'word': word.word,
            'definition': word.definition,
            'tag': word.tag
        },
        'status': f"待学习: {len(trainer.to_learn)} | 已学习: {len(trainer.learned)} | L位置={trainer.a}, M位置={trainer.b}",
        'can_undo': trainer.can_undo_last_choice()
    })

# 路由：更新参数（修改为使用全局训练器状态）
@app.route('/update_params', methods=['POST'])
@login_required
def update_params():
    data = request.json
    a = data.get('a')
    b = data.get('b')
    
    # 验证参数
    try:
        a = int(a)
        b = int(b)
        if a < 1 or b < 1 or a > 100 or b > 100:
            return jsonify({'success': False, 'message': '参数值无效'})
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': '参数值无效'})
    
    # 从全局字典获取训练器状态
    user_trainer = user_trainers.get(current_user.id)
    if not user_trainer:
        return jsonify({'success': False, 'message': '训练器未初始化'})
    
    trainer = user_trainer['trainer']
    file_id = user_trainer['file_id']
    
    # 更新参数
    trainer.a = a
    trainer.b = b
    
    # 保存训练器状态
    user_trainers[current_user.id] = user_trainer
    
    # 更新参数后保存进度
    save_trainer_progress(current_user.id, file_id)
    
    return jsonify({
        'success': True,
        'status': f"待学习: {len(trainer.to_learn)} | 已学习: {len(trainer.learned)} | L位置={trainer.a}, M位置={trainer.b}"
    })

# 路由：重置进度（修改为使用全局训练器状态）
@app.route('/reset_progress', methods=['POST'])
@login_required
def reset_progress():
    # 从全局字典获取训练器状态
    user_trainer = user_trainers.get(current_user.id)
    if not user_trainer:
        return jsonify({'success': False, 'message': '训练器未初始化'})
    
    file_id = user_trainer['file_id']
    
    # 获取文件
    file = VocabFile.query.get(file_id)
    if not file:
        return jsonify({'success': False, 'message': '文件不存在'})
    
    # 重新加载文件
    trainer = VocabularyTrainer(a=10, b=15)
    success, message = trainer.load_from_file(file.filepath)
    
    if not success:
        return jsonify({'success': False, 'message': message})
    
    # 获取下一个单词
    word = trainer.get_next_word()
    
    # 更新全局训练器状态
    user_trainers[current_user.id] = {
        'trainer': trainer,
        'file_id': file_id
    }
    
    # 重置进度后保存进度
    save_trainer_progress(current_user.id, file_id)
    
    return jsonify({
        'success': True,
        'word': {
            'word': word.word,
            'definition': word.definition,
            'tag': word.tag
        },
        'status': f"待学习: {len(trainer.to_learn)} | 已学习: {len(trainer.learned)} | L位置={trainer.a}, M位置={trainer.b}",
        'message': '进度已重置'
    })

# 路由：添加单词（修改为使用全局训练器状态）
@app.route('/add_word', methods=['POST'])
@login_required
def add_word():
    word = request.json.get('word')
    definition = request.json.get('definition')
    
    if not word or not definition:
        return jsonify({'success': False, 'message': '单词和释义不能为空'})
    
    # 从全局字典获取训练器状态
    user_trainer = user_trainers.get(current_user.id)
    if not user_trainer:
        return jsonify({'success': False, 'message': '训练器未初始化'})
    
    trainer = user_trainer['trainer']
    file_id = user_trainer['file_id']
    
    # 添加新单词
    new_word, message = trainer.add_word(word, definition)
    
    # 保存训练器状态
    user_trainers[current_user.id] = user_trainer
    
    # 添加单词后保存进度
    save_trainer_progress(current_user.id, file_id)
    
    return jsonify({
        'success': True,
        'word': {
            'word': new_word.word,
            'definition': new_word.definition,
            'tag': new_word.tag
        },
        'status': f"待学习: {len(trainer.to_learn)} | 已学习: {len(trainer.learned)} | L位置={trainer.a}, M位置={trainer.b}",
        'message': message
    })

# 路由：编辑单词（修改为使用全局训练器状态）
@app.route('/edit_word', methods=['POST'])
@login_required
def edit_word():
    new_word = request.json.get('word')
    new_definition = request.json.get('definition')
    
    if not new_word or not new_definition:
        return jsonify({'success': False, 'message': '单词和释义不能为空'})
    
    # 从全局字典获取训练器状态
    user_trainer = user_trainers.get(current_user.id)
    if not user_trainer:
        return jsonify({'success': False, 'message': '训练器未初始化'})
    
    trainer = user_trainer['trainer']
    file_id = user_trainer['file_id']
    
    # 获取当前单词
    current_word = trainer.current_word
    if not current_word:
        return jsonify({'success': False, 'message': '没有当前单词'})
    
    # 编辑单词
    current_word.word = new_word
    current_word.definition = new_definition
    
    # 保存训练器状态
    user_trainers[current_user.id] = user_trainer
    
    # 编辑单词后保存进度
    save_trainer_progress(current_user.id, file_id)
    
    return jsonify({
        'success': True,
        'word': {
            'word': current_word.word,
            'definition': current_word.definition,
            'tag': current_word.tag
        },
        'status': f"待学习: {len(trainer.to_learn)} | 已学习: {len(trainer.learned)} | L位置={trainer.a}, M位置={trainer.b}",
        'message': f"单词已更新为 '{new_word}'"
    })

# 初始化数据库
@app.before_first_request
def create_tables():
    db.drop_all()  # 删除旧表（仅在开发环境中使用）
    db.create_all()  # 创建新表

# 启动应用
if __name__ == '__main__':
    app.run(debug=True)
