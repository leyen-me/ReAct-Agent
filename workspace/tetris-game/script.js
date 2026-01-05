// 游戏常量
const COLS = 10;
const ROWS = 20;
const BLOCK_SIZE = 30;
const COLORS = [
    null,
    '#00f0f0', // I
    '#0000f0', // J
    '#f0a000', // L
    '#f0f000', // O
    '#00f000', // S
    '#a000f0', // T
    '#f00000'  // Z
];

// 方块形状
const SHAPES = [
    null,
    // I
    [
        [0, 0, 0, 0],
        [1, 1, 1, 1],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
    ],
    // J
    [
        [2, 0, 0],
        [2, 2, 2],
        [0, 0, 0]
    ],
    // L
    [
        [0, 0, 3],
        [3, 3, 3],
        [0, 0, 0]
    ],
    // O
    [
        [4, 4],
        [4, 4]
    ],
    // S
    [
        [0, 5, 5],
        [5, 5, 0],
        [0, 0, 0]
    ],
    // T
    [
        [0, 6, 0],
        [6, 6, 6],
        [0, 0, 0]
    ],
    // Z
    [
        [7, 7, 0],
        [0, 7, 7],
        [0, 0, 0]
    ]
];

// 游戏变量
let board = [];
let score = 0;
let level = 1;
let gameOver = false;
let isPaused = false;
let dropCounter = 0;
let dropInterval = 1000;
let lastTime = 0;
let player = {
    pos: { x: 0, y: 0 },
    matrix: null,
    score: 0
};

// DOM元素
const boardElement = document.getElementById('board');
const scoreElement = document.getElementById('score');
const levelElement = document.getElementById('level');
const startButton = document.getElementById('start-btn');
const pauseButton = document.getElementById('pause-btn');

// 初始化游戏
function init() {
    createBoard();
    resetGame();
    initEvents();
}

// 创建游戏面板
function createBoard() {
    boardElement.innerHTML = '';
    for (let y = 0; y < ROWS; y++) {
        const row = [];
        board.push(row);
        for (let x = 0; x < COLS; x++) {
            const cell = document.createElement('div');
            cell.classList.add('cell');
            cell.setAttribute('data-row', y);
            cell.setAttribute('data-col', x);
            boardElement.appendChild(cell);
            row.push(null);
        }
    }
}

// 重置游戏
function resetGame() {
    board.forEach(row => row.fill(null));
    score = 0;
    level = 1;
    dropInterval = 1000;
    player.score = 0;
    gameOver = false;
    isPaused = false;
    updateScore();
    spawnPiece();
    draw();
}

// 获取随机方块
function getRandomPiece() {
    const pieceId = Math.floor(Math.random() * 7) + 1;
    return {
        matrix: SHAPES[pieceId],
        type: pieceId
    };
}

// 生成新方块
function spawnPiece() {
    const piece = getRandomPiece();
    player.matrix = piece.matrix;
    player.type = piece.type;
    player.pos.y = 0;
    player.pos.x = Math.floor(COLS / 2) - Math.floor(player.matrix[0].length / 2);
    
    // 检查游戏结束
    if (collide()) {
        gameOver = true;
        alert('游戏结束! 您的得分: ' + score);
    }
}

// 碰撞检测
function collide() {
    const [m, o] = [player.matrix, player.pos];
    for (let y = 0; y < m.length; y++) {
        for (let x = 0; x < m[y].length; x++) {
            if (m[y][x] !== 0 &&
                (board[y + o.y] &&
                board[y + o.y][x + o.x]) !== null) {
                return true;
            }
        }
    }
    return false;
}

// 绘制游戏面板
function draw() {
    // 清除面板
    boardElement.querySelectorAll('.cell').forEach(cell => {
        cell.className = 'cell';
    });
    
    // 绘制固定方块
    board.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== null) {
                const cell = document.querySelector(`.cell[data-row="${y}"][data-col="${x}"]`);
                cell.classList.add('filled');
                cell.classList.add(getClassNameByType(value));
            }
        });
    });
    
    // 绘制当前方块
    player.matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                const cell = document.querySelector(`.cell[data-row="${y + player.pos.y}"][data-col="${x + player.pos.x}"]`);
                if (cell) {
                    cell.classList.add('filled');
                    cell.classList.add(getClassNameByType(player.type));
                }
            }
        });
    });
}

// 根据方块类型获取CSS类名
function getClassNameByType(type) {
    const types = [null, 'i', 'j', 'l', 'o', 's', 't', 'z'];
    return types[type];
}

// 移动方块
function move(dir) {
    player.pos.x += dir;
    if (collide()) {
        player.pos.x -= dir;
    }
}

// 旋转方块
function rotate() {
    const pos = player.pos.x;
    let offset = 1;
    rotateMatrix(player.matrix);
    while (collide()) {
        player.pos.x += offset;
        offset = -(offset + (offset > 0 ? 1 : -1));
        if (offset > player.matrix[0].length) {
            rotateMatrix(player.matrix);
            player.pos.x = pos;
            return;
        }
    }
}

// 旋转矩阵
function rotateMatrix(matrix) {
    for (let y = 0; y < matrix.length; ++y) {
        for (let x = 0; x < y; ++x) {
            [matrix[x][y], matrix[y][x]] = [matrix[y][x], matrix[x][y]];
        }
    }
    matrix.forEach(row => row.reverse());
}

// 放置方块
function place() {
    player.matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                board[y + player.pos.y][x + player.pos.x] = player.type;
            }
        });
    });
    
    // 检查是否有完整的行
    checkLines();
    
    // 生成新方块
    spawnPiece();
}

// 检查完整行
function checkLines() {
    let lineCount = 0;
    outer: for (let y = ROWS - 1; y >= 0; --y) {
        for (let x = 0; x < COLS; ++x) {
            if (board[y][x] === null) {
                continue outer;
            }
        }
        
        // 移除这一行
        const row = board.splice(y, 1)[0].fill(null);
        board.unshift(row);
        ++y;
        
        lineCount++;
    }
    
    // 更新得分
    if (lineCount > 0) {
        score += lineCount * 10 * level;
        level = Math.floor(score / 100) + 1;
        dropInterval = 1000 - (level - 1) * 100;
        updateScore();
    }
}

// 更新得分显示
function updateScore() {
    scoreElement.textContent = score;
    levelElement.textContent = level;
}

// 方块下落
function drop() {
    player.pos.y++;
    if (collide()) {
        player.pos.y--;
        place();
    }
    dropCounter = 0;
}

// 游戏循环
function update(time = 0) {
    if (gameOver || isPaused) return;
    
    const deltaTime = time - lastTime;
    lastTime = time;
    
    dropCounter += deltaTime;
    if (dropCounter > dropInterval) {
        drop();
    }
    
    draw();
    requestAnimationFrame(update);
}

// 初始化事件监听器
function initEvents() {
    document.addEventListener('keydown', event => {
        if (gameOver || isPaused) return;
        
        switch (event.keyCode) {
            case 37: // 左箭头
                move(-1);
                break;
            case 39: // 右箭头
                move(1);
                break;
            case 40: // 下箭头
                drop();
                break;
            case 38: // 上箭头
                rotate();
                break;
        }
    });
    
    startButton.addEventListener('click', () => {
        if (gameOver) {
            resetGame();
        }
        isPaused = false;
        lastTime = performance.now();
        requestAnimationFrame(update);
    });
    
    pauseButton.addEventListener('click', () => {
        isPaused = !isPaused;
        if (!isPaused && !gameOver) {
            lastTime = performance.now();
            requestAnimationFrame(update);
        }
    });
}

// 启动游戏
init();