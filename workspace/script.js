// 贪吃蛇游戏 - 现代设计版
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const scoreDisplay = document.getElementById('score');
const startBtn = document.getElementById('startBtn');
const pauseBtn = document.getElementById('pauseBtn');
const restartBtn = document.getElementById('restartBtn');
const difficultySelect = document.getElementById('difficulty');

// 游戏配置
const gridSize = 20;
const tileCount = 20;
let snake = [{x: 10, y: 10}];
let food = {x: 5, y: 5};
let dx = 0, dy = 0;
let score = 0;
let gameRunning = false;
let gamePaused = false;
let gameLoop;
let gameSpeed = 150;

// 颜色定义
const colors = {
    snakeHead: '#00ff88',
    snakeHeadDark: '#00cc66',
    snakeBody: '#00cc66',
    snakeBodyDark: '#00994d',
    snakeTail: '#006633',
    snakeTailDark: '#004422',
    food: '#ff3366',
    foodGlow: '#ff6699',
    background: '#000000',
    grid: '#1a1a1a'
};

// 难度设置
const difficulties = {
    easy: 200,
    medium: 150,
    hard: 100,
    expert: 70
};

// 生成食物
function generateFood() {
    food = {
        x: Math.floor(Math.random() * tileCount),
        y: Math.floor(Math.random() * tileCount)
    };
    // 确保食物不出现在蛇身上
    for (let s of snake) {
        if (s.x === food.x && s.y === food.y) {
            return generateFood();
        }
    }
}

// 绘制渐变背景
function drawBackground() {
    // 清空画布
    ctx.fillStyle = colors.background;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // 绘制网格线
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= tileCount; i++) {
        ctx.beginPath();
        ctx.moveTo(i * gridSize, 0);
        ctx.lineTo(i * gridSize, canvas.height);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(0, i * gridSize);
        ctx.lineTo(canvas.width, i * gridSize);
        ctx.stroke();
    }
}

// 绘制蛇
function drawSnake() {
    for (let i = 0; i < snake.length; i++) {
        const segment = snake[i];
        const x = segment.x * gridSize;
        const y = segment.y * gridSize;
        const size = gridSize - 2;
        
        // 蛇头（第一个）
        if (i === 0) {
            drawSnakeHead(x, y, size);
        }
        // 蛇尾（最后一个）
        else if (i === snake.length - 1) {
            drawSnakeTail(x, y, size);
        }
        // 蛇身（中间部分）
        else {
            drawSnakeBody(x, y, size, i);
        }
    }
}

// 绘制蛇头
function drawSnakeHead(x, y, size) {
    const centerX = x + gridSize / 2;
    const centerY = y + gridSize / 2;
    const radius = gridSize / 2 - 1;
    
    // 蛇头主体 - 圆形渐变
    const gradient = ctx.createRadialGradient(
        centerX, centerY, 0,
        centerX, centerY, radius
    );
    gradient.addColorStop(0, colors.snakeHead);
    gradient.addColorStop(1, colors.snakeHeadDark);
    
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.fill();
    
    // 蛇头眼睛
    drawSnakeEyes(x, y);
    
    // 蛇头高光
    ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.beginPath();
    ctx.arc(centerX - radius/3, centerY - radius/3, radius/4, 0, Math.PI * 2);
    ctx.fill();
}

// 绘制蛇眼睛
function drawSnakeEyes(x, y) {
    const eyeSize = gridSize / 6;
    const eyeOffset = gridSize / 3;
    
    ctx.fillStyle = '#000000';
    
    // 根据移动方向确定眼睛位置
    if (dx === 1) { // 向右
        ctx.beginPath();
        ctx.arc(x + gridSize - eyeOffset, y + eyeOffset, eyeSize, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x + gridSize - eyeOffset, y + gridSize - eyeOffset, eyeSize, 0, Math.PI * 2);
        ctx.fill();
    } else if (dx === -1) { // 向左
        ctx.beginPath();
        ctx.arc(x + eyeOffset, y + eyeOffset, eyeSize, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x + eyeOffset, y + gridSize - eyeOffset, eyeSize, 0, Math.PI * 2);
        ctx.fill();
    } else if (dy === 1) { // 向下
        ctx.beginPath();
        ctx.arc(x + eyeOffset, y + gridSize - eyeOffset, eyeSize, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x + gridSize - eyeOffset, y + gridSize - eyeOffset, eyeSize, 0, Math.PI * 2);
        ctx.fill();
    } else if (dy === -1) { // 向上
        ctx.beginPath();
        ctx.arc(x + eyeOffset, y + eyeOffset, eyeSize, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x + gridSize - eyeOffset, y + eyeOffset, eyeSize, 0, Math.PI * 2);
        ctx.fill();
    }
}

// 绘制蛇身
function drawSnakeBody(x, y, size, index) {
    // 蛇身主体 - 圆角矩形
    const cornerRadius = 4;
    
    // 创建渐变
    const gradient = ctx.createLinearGradient(x, y, x + size, y + size);
    gradient.addColorStop(0, colors.snakeBody);
    gradient.addColorStop(1, colors.snakeBodyDark);
    
    ctx.fillStyle = gradient;
    
    // 绘制圆角矩形
    ctx.beginPath();
    ctx.moveTo(x + cornerRadius, y);
    ctx.lineTo(x + size - cornerRadius, y);
    ctx.quadraticCurveTo(x + size, y, x + size, y + cornerRadius);
    ctx.lineTo(x + size, y + size - cornerRadius);
    ctx.quadraticCurveTo(x + size, y + size, x + size - cornerRadius, y + size);
    ctx.lineTo(x + cornerRadius, y + size);
    ctx.quadraticCurveTo(x, y + size, x, y + size - cornerRadius);
    ctx.lineTo(x, y + cornerRadius);
    ctx.quadraticCurveTo(x, y, x + cornerRadius, y);
    ctx.closePath();
    ctx.fill();
    
    // 蛇身细节 - 内部小圆点
    ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
    const dotSize = size * 0.2;
    const dotX = x + size / 2;
    const dotY = y + size / 2;
    
    ctx.beginPath();
    ctx.arc(dotX, dotY, dotSize, 0, Math.PI * 2);
    ctx.fill();
}

// 绘制蛇尾
function drawSnakeTail(x, y, size) {
    // 蛇尾主体 - 三角形
    ctx.fillStyle = colors.snakeTail;
    
    ctx.beginPath();
    ctx.moveTo(x + size/2, y);
    ctx.lineTo(x + size, y + size/2);
    ctx.lineTo(x + size/2, y + size);
    ctx.lineTo(x, y + size/2);
    ctx.closePath();
    ctx.fill();
    
    // 蛇尾细节 - 内部小三角形
    ctx.fillStyle = colors.snakeTailDark;
    const innerSize = size * 0.6;
    const innerX = x + (size - innerSize)/2;
    const innerY = y + (size - innerSize)/2;
    
    ctx.beginPath();
    ctx.moveTo(innerX + innerSize/2, innerY);
    ctx.lineTo(innerX + innerSize, innerY + innerSize/2);
    ctx.lineTo(innerX + innerSize/2, innerY + innerSize);
    ctx.lineTo(innerX, innerY + innerSize/2);
    ctx.closePath();
    ctx.fill();
}

// 绘制食物
function drawFood() {
    const centerX = food.x * gridSize + gridSize / 2;
    const centerY = food.y * gridSize + gridSize / 2;
    const radius = gridSize / 2 - 1;
    
    // 食物发光效果
    const glow = ctx.createRadialGradient(
        centerX, centerY, 0,
        centerX, centerY, radius * 1.5
    );
    glow.addColorStop(0, colors.foodGlow);
    glow.addColorStop(0.7, colors.food);
    glow.addColorStop(1, 'rgba(255, 51, 102, 0)');
    
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius * 1.5, 0, Math.PI * 2);
    ctx.fill();
    
    // 食物主体 - 苹果形状
    ctx.fillStyle = colors.food;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.fill();
    
    // 食物高光
    ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.beginPath();
    ctx.arc(centerX - radius/3, centerY - radius/3, radius/4, 0, Math.PI * 2);
    ctx.fill();
    
    // 苹果柄
    ctx.strokeStyle = '#663300';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY - radius);
    ctx.lineTo(centerX, centerY - radius - 3);
    ctx.stroke();
}

// 绘制游戏
function draw() {
    drawBackground();
    drawSnake();
    drawFood();
}

// 更新游戏状态
function update() {
    if (!gameRunning || gamePaused) return;
    
    // 计算新的蛇头位置
    const head = {x: snake[0].x + dx, y: snake[0].y + dy};
    
    // 检查碰撞
    if (head.x < 0 || head.x >= tileCount || head.y < 0 || head.y >= tileCount) {
        gameOver();
        return;
    }
    
    // 检查是否撞到自己
    for (let s of snake) {
        if (s.x === head.x && s.y === head.y) {
            gameOver();
            return;
        }
    }
    
    // 移动蛇
    snake.unshift(head);
    
    // 检查是否吃到食物
    if (head.x === food.x && head.y === food.y) {
        score += 10;
        scoreDisplay.textContent = `得分: ${score}`;
        generateFood();
        
        // 每得50分增加速度
        if (score % 50 === 0) {
            gameSpeed = Math.max(50, gameSpeed - 10);
            clearInterval(gameLoop);
            gameLoop = setInterval(updateAndDraw, gameSpeed);
        }
    } else {
        // 没吃到食物就移除尾部
        snake.pop();
    }
}

// 更新并绘制
function updateAndDraw() {
    update();
    draw();
}

// 游戏结束
function gameOver() {
    clearInterval(gameLoop);
    gameRunning = false;
    startBtn.innerHTML = '<i class="fas fa-play"></i> 开始游戏';
    
    // 现代风格的提示框
    const gameOverDiv = document.createElement('div');
    gameOverDiv.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: rgba(26, 26, 26, 0.95);
        padding: 30px;
        border-radius: 15px;
        border: 2px solid #ff3366;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.7);
        z-index: 1000;
        text-align: center;
        min-width: 300px;
    `;
    
    gameOverDiv.innerHTML = `
        <h2 style="color: #ff3366; margin-bottom: 15px;">游戏结束！</h2>
        <p style="color: #ffffff; font-size: 1.2rem; margin-bottom: 10px;">最终得分: <span style="color: #00ff88; font-weight: bold;">${score}</span></p>
        <p style="color: #cccccc; margin-bottom: 20px;">蛇身长度: ${snake.length}</p>
        <button id="closeGameOver" style="
            background: linear-gradient(135deg, #00ff88, #00cc66);
            color: #000;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
        ">确定</button>
    `;
    
    document.body.appendChild(gameOverDiv);
    
    document.getElementById('closeGameOver').addEventListener('click', () => {
        document.body.removeChild(gameOverDiv);
    });
}

// 开始游戏
function startGame() {
    if (gameRunning) return;
    
    // 重置游戏状态
    snake = [{x: 10, y: 10}];
    dx = 1;  // 初始向右移动
    dy = 0;
    score = 0;
    scoreDisplay.textContent = '得分: 0';
    
    // 设置游戏速度
    const difficulty = difficultySelect.value;
    gameSpeed = difficulties[difficulty];
    
    generateFood();
    gameRunning = true;
    gamePaused = false;
    pauseBtn.innerHTML = '<i class="fas fa-pause"></i> 暂停';
    startBtn.innerHTML = '<i class="fas fa-gamepad"></i> 游戏中';
    
    // 开始游戏循环
    clearInterval(gameLoop);
    gameLoop = setInterval(updateAndDraw, gameSpeed);
}

// 暂停/继续游戏
function togglePause() {
    if (!gameRunning) return;
    
    gamePaused = !gamePaused;
    pauseBtn.innerHTML = gamePaused ? '<i class="fas fa-play"></i> 继续' : '<i class="fas fa-pause"></i> 暂停';
    
    if (!gamePaused) {
        draw();
    }
}

// 重新开始游戏
function restartGame() {
    clearInterval(gameLoop);
    gameRunning = false;
    gamePaused = false;
    startGame();
}

// 键盘控制
document.addEventListener('keydown', e => {
    if (!gameRunning) {
        startGame();
        return;
    }
    
    // 防止反向移动
    if (e.key === 'ArrowUp' && dy !== 1) {
        dx = 0;
        dy = -1;
    } else if (e.key === 'ArrowDown' && dy !== -1) {
        dx = 0;
        dy = 1;
    } else if (e.key === 'ArrowLeft' && dx !== 1) {
        dx = -1;
        dy = 0;
    } else if (e.key === 'ArrowRight' && dx !== -1) {
        dx = 1;
        dy = 0;
    } else if (e.key === ' ' || e.key === 'p') {
        // 空格或P键暂停
        togglePause();
    }
});

// 按钮事件监听
startBtn.addEventListener('click', startGame);
pauseBtn.addEventListener('click', togglePause);
restartBtn.addEventListener('click', restartGame);
difficultySelect.addEventListener('change', () => {
    if (gameRunning) {
        const difficulty = difficultySelect.value;
        gameSpeed = difficulties[difficulty];
        clearInterval(gameLoop);
        gameLoop = setInterval(updateAndDraw, gameSpeed);
    }
});

// 初始绘制
draw();