// 简单的贪吃蛇游戏实现

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const gridSize = 20;                // 每格像素大小
const tileCount = canvas.width / gridSize; // 行/列数

let snake = [{x: 10, y: 10}]; // 初始蛇身（只有一个块）
let velocity = {x: 0, y: 0}; // 当前移动方向
let food = {x: 5, y: 5}; // 食物位置
let speed = 150; // 游戏刷新间隔（毫秒）
let growing = false;

// 随机生成食物位置，确保不与蛇身重叠
function placeFood() {
    food.x = Math.floor(Math.random() * tileCount);
    food.y = Math.floor(Math.random() * tileCount);
    // 若生成的食物在蛇身上，重新生成
    if (snake.some(segment => segment.x === food.x && segment.y === food.y)) {
        placeFood();
    }
}

function gameLoop() {
    // 更新蛇的位置
    const head = {x: snake[0].x + velocity.x, y: snake[0].y + velocity.y};

    // 边界碰撞检测（穿墙模式：从另一侧出现）
    if (head.x < 0) head.x = tileCount - 1;
    if (head.x >= tileCount) head.x = 0;
    if (head.y < 0) head.y = tileCount - 1;
    if (head.y >= tileCount) head.y = 0;

    // 检测是否吃到自己（忽略头部本身）
    if (snake.length > 1 && snake.slice(1).some(segment => segment.x === head.x && segment.y === head.y)) {
        alert('游戏结束！');
        resetGame();
        return;
    }

    snake.unshift(head); // 将新头部加入数组前端

    // 检测是否吃到食物
    if (head.x === food.x && head.y === food.y) {
        growing = true;
        placeFood();
    }

    if (!growing) {
        snake.pop(); // 移除尾巴，使长度保持不变
    } else {
        growing = false; // 吃到食物后本次不移除尾巴，使蛇长一格
    }

    drawGame();
}

function drawGame() {
    // 清空画布
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 绘制食物
    ctx.fillStyle = 'red';
    ctx.fillRect(food.x * gridSize, food.y * gridSize, gridSize, gridSize);

    // 绘制蛇身
    ctx.fillStyle = 'green';
    snake.forEach((segment, index) => {
        ctx.fillRect(segment.x * gridSize, segment.y * gridSize, gridSize, gridSize);
    });
}

function resetGame() {
    snake = [{x: 10, y: 10}];
    velocity = {x: 0, y: 0};
    placeFood();
}

// 键盘控制方向（防止 180 度瞬间反向导致死亡）
window.addEventListener('keydown', e => {
    switch (e.key) {
        case 'ArrowUp':
            if (velocity.y === 1) break; // 正在向下，不能直接向上
            velocity = {x: 0, y: -1};
            break;
        case 'ArrowDown':
            if (velocity.y === -1) break;
            velocity = {x: 0, y: 1};
            break;
        case 'ArrowLeft':
            if (velocity.x === 1) break;
            velocity = {x: -1, y: 0};
            break;
        case 'ArrowRight':
            if (velocity.x === -1) break;
            velocity = {x: 1, y: 0};
            break;
    }
});

// 启动游戏循环
placeFood();
setInterval(gameLoop, speed);
