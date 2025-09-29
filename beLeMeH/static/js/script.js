document.addEventListener('DOMContentLoaded', function() {
    // 更新单词显示
    function updateWordDisplay(word) {
        document.querySelector('.word').textContent = word.word;
    }
    
    // 更新状态显示
    function updateStatusDisplay(status) {
        document.querySelector('.status-display span').textContent = status;
    }
    
    // 更新标签显示
    function updateTagDisplay(tag) {
        document.querySelector('.tag-display span').textContent = `标签: ${tag}`;
    }
    
    // 删除文件按钮
    document.querySelectorAll('.delete-file').forEach(button => {
        button.addEventListener('click', function() {
            const fileId = this.dataset.fileId;
            const isPublic = this.dataset.isPublic === '1';
            const msg = isPublic
                ? '该文件为公开文件，同时会从公共文档库移除。确定删除吗？'
                : '确定要删除这个文件吗？这将永久删除文件及其所有学习进度。';

            if (confirm(msg)) {
                fetch('/delete_file/' + fileId, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(data.message);
                        // 刷新页面
                        location.reload();
                    } else {
                        alert(data.message);
                    }
                });
            }
        });
    });
    
    // 处理选择按钮点击
    document.querySelectorAll('.choice-btn').forEach(button => {
        button.addEventListener('click', function() {
            const choice = this.dataset.choice;
            
            // 如果是"已掌握"按钮
            if (!choice) {
                markAsLearned();
                return;
            }
            
            // 发送选择到服务器
            fetch('/process_choice', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    choice: choice
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // 更新界面
                    updateWordDisplay(data.word);
                    updateStatusDisplay(data.status);
                    updateTagDisplay(data.word.tag);
                    
                    // 显示释义
                    document.querySelector('.definition-content').textContent = data.word.definition;
                    
                    // 设置按钮状态：选择后释义出现，选择按钮禁用，上一个按钮不可用，下一个按钮可用
                    setButtonStates(false, false, true);
                } else {
                    alert(data.message);
                }
            });
        });
    });
    
    // 下一个单词按钮
    document.querySelector('.action-btn.next').addEventListener('click', function() {
        fetch('/next_word')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 更新单词显示
                document.querySelector('.word').textContent = data.word.word;
                
                // 清空释义
                document.querySelector('.definition-content').textContent = '';
                
                // 更新标签显示
                document.querySelector('.tag-display span').textContent = `标签: ${data.word.tag}`;
                
                // 更新状态显示
                document.querySelector('.status-display span').textContent = data.status;
                
                // 设置按钮状态：新单词出现，可以选择熟悉度，上一个按钮可用，下一个按钮不可用
                setButtonStates(true, true, false);
            } else {
                alert(data.message);
            }
        });
    });
    
    // 上一个单词按钮
    document.querySelector('.action-btn.prev').addEventListener('click', function() {
        fetch('/prev_word')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 更新单词显示
                document.querySelector('.word').textContent = data.word.word;
                
                // 更新标签显示
                document.querySelector('.tag-display span').textContent = `标签: ${data.word.tag}`;
                
                // 更新状态显示
                document.querySelector('.status-display span').textContent = data.status;
                
                // 清空释义（上一个单词时不显示释义）
                document.querySelector('.definition-content').textContent = '';
                
                // 设置按钮状态：上一个单词出现，可以选择熟悉度，上一个按钮不可用，下一个按钮不可用
                setButtonStates(true, false, false);
            } else {
                alert(data.message);
            }
        });
    });
    
    // 标记为已掌握
    function markAsLearned() {
        fetch('/mark_learned', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 更新单词显示
                document.querySelector('.word').textContent = data.word.word;
                
                // 更新标签显示
                document.querySelector('.tag-display span').textContent = `标签: ${data.word.tag}`;
                
                // 更新状态显示
                document.querySelector('.status-display span').textContent = data.status;
                
                // 显示释义
                document.querySelector('.definition-content').textContent = data.word.definition;
                
                // 设置按钮状态：标记已掌握后，选择按钮禁用，上一个按钮不可用，下一个按钮可用
                setButtonStates(false, false, true);
            } else {
                alert(data.message);
            }
        });
    }
    
    // 重置进度按钮
    document.querySelector('.bottom-btn.reset').addEventListener('click', function() {
        if (confirm('确定要重置学习进度吗？这将删除所有保存的数据并重新开始。')) {
            fetch('/reset_progress', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // 更新单词显示
                    document.querySelector('.word').textContent = data.word.word;
                    
                    // 更新标签显示
                    document.querySelector('.tag-display span').textContent = `标签: ${data.word.tag}`;
                    
                    // 更新状态显示
                    document.querySelector('.status-display span').textContent = data.status;
                    
                    // 清空释义
                    document.querySelector('.definition-content').textContent = '';
                    
                    // 启用选择按钮
                    document.querySelectorAll('.choice-btn').forEach(btn => {
                        btn.disabled = false;
                    });
                    
                    // 禁用下一个按钮
                    document.querySelector('.action-btn.next').disabled = true;
                    
                    alert(data.message);
                } else {
                    alert(data.message);
                }
            });
        }
    });
    
    // 添加单词按钮
    document.querySelector('.bottom-btn.add').addEventListener('click', function() {
        const word = prompt('请输入单词:');
        if (!word) return;
        
        const definition = prompt('请输入释义:');
        if (!definition) return;
        
        fetch('/add_word', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                word: word,
                definition: definition
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 更新单词显示
                document.querySelector('.word').textContent = data.word.word;
                
                // 更新标签显示
                document.querySelector('.tag-display span').textContent = `标签: ${data.word.tag}`;
                
                // 更新状态显示
                document.querySelector('.status-display span').textContent = data.status;
                
                alert(data.message);
            } else {
                alert(data.message);
            }
        });
    });
    
    // 编辑单词按钮
    document.querySelector('.bottom-btn.edit').addEventListener('click', function() {
        const currentWord = document.querySelector('.word').textContent;
        const newWord = prompt('编辑单词:', currentWord);
        if (!newWord) return;
        
        const currentDefinition = document.querySelector('.definition-content').textContent;
        const newDefinition = prompt('编辑释义:', currentDefinition);
        if (!newDefinition) return;
        
        fetch('/edit_word', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                word: newWord,
                definition: newDefinition
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 更新单词显示
                document.querySelector('.word').textContent = data.word.word;
                
                // 更新标签显示
                document.querySelector('.tag-display span').textContent = `标签: ${data.word.tag}`;
                
                // 更新状态显示
                document.querySelector('.status-display span').textContent = data.status;
                
                // 更新释义
                document.querySelector('.definition-content').textContent = data.word.definition;
                
                alert(data.message);
            } else {
                alert(data.message);
            }
        });
    });
    
    // 退出按钮（如果存在的话）
    const exitBtn = document.querySelector('.bottom-btn.exit');
    if (exitBtn) {
        exitBtn.addEventListener('click', function() {
            fetch('/exit_trainer', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(data.message);
                    // 重定向到首页
                    window.location.href = '/';
                } else {
                    alert(data.message);
                }
            });
        });
    }
    
    // 按钮状态管理函数
    function setButtonStates(enableChoices, enablePrevious, enableNext) {
        // 熟悉度按钮和已掌握按钮
        document.querySelectorAll('.choice-btn, .action-btn.learned').forEach(btn => {
            btn.disabled = !enableChoices;
            btn.style.opacity = enableChoices ? '1' : '0.5';
        });
        
        // 上一个按钮
        const prevBtn = document.querySelector('.action-btn.prev');
        if (prevBtn) {
            prevBtn.disabled = !enablePrevious;
            prevBtn.style.opacity = enablePrevious ? '1' : '0.5';
        }
        
        // 下一个按钮
        const nextBtn = document.querySelector('.action-btn.next');
        if (nextBtn) {
            nextBtn.disabled = !enableNext;
            nextBtn.style.opacity = enableNext ? '1' : '0.5';
        }
    }
    
    // 实时参数更新系统
    let updateTimeout = null; // 防抖延迟计时器
    
    // 等待页面完全加载后执行
    setTimeout(function() {
        // 查找参数输入框
        const aParam = document.getElementById('a-param');
        const bParam = document.getElementById('b-param');
        
        if (!aParam || !bParam) {
            return;
        }
        
        // 绑定实时更新事件
        aParam.oninput = updateParamsRealtime;
        bParam.oninput = updateParamsRealtime;
        
    }, 500); // 延迟500ms确保所有元素都已加载
    
    // 页面加载完成后的初始化
    document.addEventListener('DOMContentLoaded', function() {
        // 初始状态设置：新单词刚出现时，可以选择熟悉度，上一个按钮可用，下一个按钮不可用
        setButtonStates(true, true, false);
        
        // 初始时清空释义
        document.querySelector('.definition-content').textContent = '';
    });
    
    function updateParamsRealtime() {
        // 防抖：如果用户正在快速输入，延迟更新
        clearTimeout(updateTimeout);
        updateTimeout = setTimeout(() => {
            const a = document.getElementById('a-param').value;
            const b = document.getElementById('b-param').value;
            
            // 验证输入值是否有效
            if (!a || !b || a < 1 || b < 1 || a > 100 || b > 100) {
                return; // 无效值时不更新
            }
            
            fetch('/update_params', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    a: parseInt(a),
                    b: parseInt(b)
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // 更新状态显示
                    document.querySelector('.status-display span').textContent = data.status;
                }
            })
            .catch(error => {
                console.error('更新参数失败:', error);
            });
        }, 300); // 300ms防抖延迟
    }
});
