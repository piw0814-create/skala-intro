import pygame
import random

pygame.init()

# -------------------------
# 화면 설정
# -------------------------
CELL = 30
COLS = 10
ROWS = 20

BOARD_X = 180
BOARD_Y = 20

WIDTH = 520
HEIGHT = ROWS * CELL + 40

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Tetris")

clock = pygame.time.Clock()
font = pygame.font.SysFont("arial", 22)

# -------------------------
# 색상
# -------------------------
BLACK = (20,20,20)
WHITE = (255,255,255)
GRAY = (80,80,80)

COLORS = [
    (0,255,255),
    (0,0,255),
    (255,165,0),
    (255,255,0),
    (0,255,0),
    (128,0,128),
    (255,0,0)
]

# -------------------------
# 블록 모양
# -------------------------
SHAPES = [

[[1,1,1,1]],

[[1,0,0],
 [1,1,1]],

[[0,0,1],
 [1,1,1]],

[[1,1],
 [1,1]],

[[0,1,1],
 [1,1,0]],

[[0,1,0],
 [1,1,1]],

[[1,1,0],
 [0,1,1]]

]

# -------------------------
# 보드
# -------------------------
board = [[0 for _ in range(COLS)] for _ in range(ROWS)]

# -------------------------
# 블록 클래스
# -------------------------
class Piece:

    def __init__(self, shape, color):
        self.shape = shape
        self.color = color
        self.x = 3
        self.y = 0

def rotate(shape):
    return [list(row) for row in zip(*shape[::-1])]

def valid(piece, dx=0, dy=0, newshape=None):

    shape = newshape if newshape else piece.shape

    for y,row in enumerate(shape):
        for x,val in enumerate(row):

            if val:

                nx = piece.x+x+dx
                ny = piece.y+y+dy

                if nx<0 or nx>=COLS:
                    return False

                if ny>=ROWS:
                    return False

                if ny>=0 and board[ny][nx]:
                    return False

    return True

def merge(piece):

    for y,row in enumerate(piece.shape):
        for x,val in enumerate(row):
            if val:
                board[piece.y+y][piece.x+x]=piece.color

def clear_lines():

    global board

    new=[]

    removed=0

    for row in board:
        if 0 not in row:
            removed+=1
        else:
            new.append(row)

    while len(new)<ROWS:
        new.insert(0,[0]*COLS)

    board=new

    return removed

def new_piece():

    i=random.randrange(len(SHAPES))
    return Piece(SHAPES[i],COLORS[i])

current = new_piece()
next_piece = new_piece()

fall_time = 0
speed = 500

gameover=False

# -------------------------
# 메인 반복
# -------------------------
running=True

while running:

    dt=clock.tick(60)
    fall_time+=dt

    for event in pygame.event.get():

        if event.type==pygame.QUIT:
            running=False

        if event.type==pygame.KEYDOWN and not gameover:

            if event.key==pygame.K_LEFT:

                if valid(current,dx=-1):
                    current.x-=1

            elif event.key==pygame.K_RIGHT:

                if valid(current,dx=1):
                    current.x+=1

            elif event.key==pygame.K_DOWN:

                if valid(current,dy=1):
                    current.y+=1

            elif event.key==pygame.K_UP:

                r=rotate(current.shape)

                if valid(current,newshape=r):
                    current.shape=r

            elif event.key==pygame.K_SPACE:

                while valid(current,dy=1):
                    current.y+=1

                merge(current)
                clear_lines()

                current=next_piece
                next_piece=new_piece()

                if not valid(current):
                    gameover=True

    if not gameover and fall_time>speed:

        fall_time=0

        if valid(current,dy=1):
            current.y+=1

        else:

            merge(current)
            clear_lines()

            current=next_piece
            next_piece=new_piece()

            if not valid(current):
                gameover=True

    # -------------------------
    # 화면 그리기
    # -------------------------

    screen.fill(BLACK)

    # NEXT
    text=font.render("NEXT",True,WHITE)
    screen.blit(text,(25,20))

    for y,row in enumerate(next_piece.shape):
        for x,val in enumerate(row):
            if val:
                pygame.draw.rect(
                    screen,
                    next_piece.color,
                    (
                        40+x*CELL,
                        70+y*CELL,
                        CELL-1,
                        CELL-1
                    )
                )

    # 보드

    pygame.draw.rect(
        screen,
        WHITE,
        (
            BOARD_X,
            BOARD_Y,
            COLS*CELL,
            ROWS*CELL
        ),
        2
    )

    for y in range(ROWS):
        for x in range(COLS):

            if board[y][x]:

                pygame.draw.rect(
                    screen,
                    board[y][x],
                    (
                        BOARD_X+x*CELL,
                        BOARD_Y+y*CELL,
                        CELL-1,
                        CELL-1
                    )
                )

            pygame.draw.rect(
                screen,
                GRAY,
                (
                    BOARD_X+x*CELL,
                    BOARD_Y+y*CELL,
                    CELL,
                    CELL
                ),
                1
            )

    # 현재 블록

    for y,row in enumerate(current.shape):
        for x,val in enumerate(row):
            if val:
                pygame.draw.rect(
                    screen,
                    current.color,
                    (
                        BOARD_X+(current.x+x)*CELL,
                        BOARD_Y+(current.y+y)*CELL,
                        CELL-1,
                        CELL-1
                    )
                )

    if gameover:

        over=font.render("GAME OVER",True,(255,0,0))
        screen.blit(over,(210,300))

    pygame.display.flip()

pygame.quit()