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
            
            if (confirm('确定要删除这个文件吗？这将永久删除文件及其所有学习进度。')) {
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
                    
                    // 禁用选择按钮
                    document.querySelectorAll('.choice-btn').forEach(btn => {
                        btn.disabled = true;
                    });
                    
                    // 启用下一个按钮
                    document.querySelector('.action-btn.next').disabled = false;
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
                
                // 重要：启用选择按钮
                document.querySelectorAll('.choice-btn').forEach(btn => {
                    btn.disabled = false;
                });
                
                // 禁用下一个按钮
                this.disabled = true;
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
                
                // 显示释义
                document.querySelector('.definition-content').textContent = data.word.definition;
                
                // 启用选择按钮
                document.querySelectorAll('.choice-btn').forEach(btn => {
                    btn.disabled = false;
                });
                
                // 禁用下一个按钮
                document.querySelector('.action-btn.next').disabled = true;
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
                
                // 禁用所有按钮
                document.querySelectorAll('.choice-btn').forEach(btn => {
                    btn.disabled = true;
                });
                
                // 启用下一个按钮
                document.querySelector('.action-btn.next').disabled = false;
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
    
    // 退出按钮
    document.querySelector('.bottom-btn.exit').addEventListener('click', function() {
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
    
    // 参数更新
    document.getElementById('a-param').addEventListener('change', updateParams);
    document.getElementById('b-param').addEventListener('change', updateParams);
    
    function updateParams() {
        const a = document.getElementById('a-param').value;
        const b = document.getElementById('b-param').value;
        
        fetch('/update_params', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                a: a,
                b: b
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.querySelector('.status-display span').textContent = data.status;
            } else {
                alert(data.message);
            }
        });
    }
});