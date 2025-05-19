import sqlite3
import logging
import os
import json
from abc import abstractmethod
import pygame as pg
from pygame.locals import *
from . import constants as c
logger = logging.getLogger("main") 

class UserDataDB:  
    def __init__(self, db_path):  
        """初始化数据库连接"""  
        self.db_path = db_path  
        self.conn = None  
        self.cursor = None  
        self.connect()  
        self.create_tables()  
    
    def connect(self):  
        """建立数据库连接"""  
        try:  
            # 确保数据库目录存在  
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)  
            self.conn = sqlite3.connect(self.db_path)  
            self.cursor = self.conn.cursor()  
        except Exception as e:  
            logger.error(f"数据库连接失败: {e}")  
            raise  
    
    def create_tables(self):  
        """创建所需的数据表"""  
        try:  
            # 创建关卡进度表  
            self.cursor.execute('''  
            CREATE TABLE IF NOT EXISTS level_progress (  
                id INTEGER PRIMARY KEY AUTOINCREMENT,  
                level_num INTEGER,  
                littlegame_num INTEGER  
            )  
            ''')  
            
            # 创建成就表  
            self.cursor.execute('''  
            CREATE TABLE IF NOT EXISTS achievements (  
                id INTEGER PRIMARY KEY AUTOINCREMENT,  
                level_completions INTEGER,  
                littlegame_completions INTEGER  
            )  
            ''')  
            
            # 创建玩家设置表  
            self.cursor.execute('''  
            CREATE TABLE IF NOT EXISTS player_settings (  
                id INTEGER PRIMARY KEY AUTOINCREMENT,  
                game_rate REAL,  
                sound_volume REAL  
            )  
            ''')  
            
            self.conn.commit()  
        except Exception as e:  
            logger.error(f"创建表失败: {e}")  
            self.conn.rollback()  
            raise  
    
    def get_user_data(self):  
        """从数据库获取所有用户数据，合并为一个字典"""  
        try:  
            user_data = {}  
            
            # 获取关卡进度  
            self.cursor.execute("SELECT level_num, littlegame_num FROM level_progress ORDER BY id DESC LIMIT 1")  
            row = self.cursor.fetchone()  
            if row:  
                user_data[c.LEVEL_NUM] = row[0]  
                user_data[c.LITTLEGAME_NUM] = row[1]  
            
            # 获取成就数据  
            self.cursor.execute("SELECT level_completions, littlegame_completions FROM achievements ORDER BY id DESC LIMIT 1")  
            row = self.cursor.fetchone()  
            if row:  
                user_data[c.LEVEL_COMPLETIONS] = row[0]  
                user_data[c.LITTLEGAME_COMPLETIONS] = row[1]  
            
            # 获取玩家设置  
            self.cursor.execute("SELECT game_rate, sound_volume FROM player_settings ORDER BY id DESC LIMIT 1")  
            row = self.cursor.fetchone()  
            if row:  
                user_data[c.GAME_RATE] = row[0]  
                user_data[c.SOUND_VOLUME] = row[1]  
            
            return user_data  
        except Exception as e:  
            logger.error(f"获取用户数据失败: {e}")  
            return {}  
    
    def save_user_data(self, game_info):  
        """保存用户数据到三个不同的表"""  
        try:  
            # 开始事务  
            self.conn.execute("BEGIN TRANSACTION")  
            
            # 保存关卡进度  
            self.cursor.execute(  
                "INSERT INTO level_progress (level_num, littlegame_num) VALUES (?, ?)",  
                (game_info.get(c.LEVEL_NUM), game_info.get(c.LITTLEGAME_NUM))  
            )  
            
            # 保存成就数据  
            self.cursor.execute(  
                "INSERT INTO achievements (level_completions, littlegame_completions) VALUES (?, ?)",  
                (game_info.get(c.LEVEL_COMPLETIONS), game_info.get(c.LITTLEGAME_COMPLETIONS))  
            )  
            
            # 保存玩家设置  
            self.cursor.execute(  
                "INSERT INTO player_settings (game_rate, sound_volume) VALUES (?, ?)",  
                (game_info.get(c.GAME_RATE), game_info.get(c.SOUND_VOLUME))  
            )  
            
            # 提交事务  
            self.conn.commit()  
        except Exception as e:  
            logger.error(f"保存用户数据失败: {e}")  
            self.conn.rollback()  
            raise  
    
    def close(self):  
        """关闭数据库连接"""  
        if self.conn:  
            self.conn.close()  

# 状态机 抽象基类
class State():
    def __init__(self):
        self.current_time = 0
        self.done = False   # false 代表未做完
        self.next = None    # 表示这个状态退出后要转到的下一个状态
        self.persist = {}   # 在状态间转换时需要传递的数据
        self.db = None

    # 当从其他状态进入这个状态时，需要进行的初始化操作
    @abstractmethod
    def startup(self, current_time:int, persist:dict):
        # 前面加了@abstractmethod表示抽象基类中必须要重新定义的method（method是对象和函数的结合）
        pass
    # 当从这个状态退出时，需要进行的清除操作
    def cleanup(self):
        self.done = False
        return self.persist
    # 在这个状态运行时进行的更新操作
    @abstractmethod
    def update(self, surface:pg.Surface, keys, current_time:int):
        # 前面加了@abstractmethod表示抽象基类中必须要重新定义的method
        pass

    # 用户数据保存函数
    def saveUserData(self):
        try:  
            if hasattr(self, 'db') and self.db is not None:  
                self.db.save_user_data(self.game_info)  
            else:  
                logger.warning("无法保存用户数据：数据库连接不存在")  
        except Exception as e:  
            logger.error(f"保存用户数据失败: {e}") 

# 进行游戏控制 循环 事件响应
class Control():
    def __init__(self):
        self.screen = pg.display.get_surface()
        self.done = False
        self.clock = pg.time.Clock()    # 创建一个对象来帮助跟踪时间
        self.keys = pg.key.get_pressed()
        self.mouse_pos = None
        self.mouse_click = [False, False]  # value:[left mouse click, right mouse click]
        self.current_time = 0.0
        self.state_dict = {}
        self.state_name = None
        self.state = None

        self.loadUserData()
        # 存档内不包含即时游戏时间信息，需要新建
        self.game_info[c.CURRENT_TIME] = 0

        # 50为目前的基础帧率，乘以倍率即是游戏帧率
        self.fps = 120 * self.game_info[c.GAME_RATE]

    def loadUserData(self):  
        try:  
            # 初始化数据库连接  
            self.db = UserDataDB(c.DB_PATH)  
            
            # 从数据库获取用户数据  
            userdata = self.db.get_user_data()  
            
            # 如果数据库为空（没有返回足够的数据），设置初始化数据  
            if len(userdata) < len(c.INIT_USERDATA):  
                self.setupUserData()  
            else:  
                self.game_info = {}  
                
                # 检查并确保所有必要的键存在  
                for key in c.INIT_USERDATA:  
                    if key in userdata:  
                        self.game_info[key] = userdata[key]  
                    else:  
                        self.game_info[key] = c.INIT_USERDATA[key]  
                
                # 由于我们现在使用的是分表存储，不需要进行部分更新  
                    
        except Exception as e:  
            logger.error(f"加载用户数据失败: {e}")  
            self.setupUserData()

    def cleanup(self):  
        if hasattr(self, 'db') and self.db is not None:  
            self.db.close()  

    def saveUserData(self):  
        try:  
            # 确保数据库连接存在  
            if not hasattr(self, 'db') or self.db is None:  
                self.db = UserDataDB(c.DB_PATH)  
            
            # 保存数据到数据库  
            self.db.save_user_data(self.game_info)  
            
        except Exception as e:  
            logger.error(f"保存用户数据失败: {e}")  

    def setupUserData(self):  
        """初始化用户数据到三个不同的表"""  
        try:  
            # 确保数据库连接存在  
            if not hasattr(self, 'db') or self.db is None:  
                # 确保数据库目录存在  
                db_dir = os.path.dirname(c.DB_PATH)  
                if not os.path.exists(db_dir):  
                    os.makedirs(db_dir)  
                
                self.db = UserDataDB(c.DB_PATH)  
            
            # 清空所有表，以便全新初始化  
            self.db.cursor.execute("DELETE FROM level_progress")  
            self.db.cursor.execute("DELETE FROM achievements")  
            self.db.cursor.execute("DELETE FROM player_settings")  
            
            # 插入初始化数据到各个表  
            # 关卡进度表  
            self.db.cursor.execute(  
                "INSERT INTO level_progress (level_num, littlegame_num) VALUES (?, ?)",  
                (c.INIT_USERDATA[c.LEVEL_NUM], c.INIT_USERDATA[c.LITTLEGAME_NUM])  
            )  
            
            # 成就表  
            self.db.cursor.execute(  
                "INSERT INTO achievements (level_completions, littlegame_completions) VALUES (?, ?)",  
                (c.INIT_USERDATA[c.LEVEL_COMPLETIONS], c.INIT_USERDATA[c.LITTLEGAME_COMPLETIONS])  
            )  
            
            # 玩家设置表  
            self.db.cursor.execute(  
                "INSERT INTO player_settings (game_rate, sound_volume) VALUES (?, ?)",  
                (c.INIT_USERDATA[c.GAME_RATE], c.INIT_USERDATA[c.SOUND_VOLUME])  
            )  
            
            # 提交事务  
            self.db.conn.commit()  
            
            # 更新内存中的游戏信息  
            self.game_info = c.INIT_USERDATA.copy()  
            
            logger.info("用户数据已初始化")  
            
        except Exception as e:  
            logger.error(f"初始化用户数据失败: {e}")  
            if hasattr(self, 'db') and self.db.conn:  
                self.db.conn.rollback()  
            raise 

    def setup_states(self, state_dict:dict, start_state):
        self.state_dict = state_dict
        self.state_name = start_state
        self.state = self.state_dict[self.state_name]
        if hasattr(self.state, 'db'):  
            self.state.db = self.db  
        self.state.startup(self.current_time, self.game_info)

    def run(self):
        while not self.done:
            self.event_loop()
            self.update()
            pg.display.update()
            self.postUpdate()

    def update(self):
        # 自 pygame_init() 调用以来的毫秒数 * 游戏速度倍率，即游戏时间
        self.current_time = pg.time.get_ticks() * self.game_info[c.GAME_RATE]

        if self.state.done:
            self.flip_state()
        self.state.update(self.screen, self.current_time, self.mouse_pos, self.mouse_click)

    def postUpdate(self):
        self.mouse_pos = None
        self.mouse_click[0] = False
        self.mouse_click[1] = False

        self.clock.tick(self.fps)

    def event_loop(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.done = True
            elif event.type == pg.KEYDOWN:
                self.keys = pg.key.get_pressed()
                if event.key == pg.K_f:
                    pg.display.set_mode(c.SCREEN_SIZE, pg.HWSURFACE|pg.FULLSCREEN)
                elif event.key == pg.K_u:
                    pg.display.set_mode(c.SCREEN_SIZE)
                elif event.key == pg.K_p:
                    self.state.next = c.GAME_VICTORY
                    self.state.done = True
                elif event.key == pg.K_l:
                    self.state.next = c.GAME_LOSE
                    self.state.done = True
                elif event.key == pg.K_a:
                    self.state.next = c.AWARD_SCREEN
                    self.state.done = True
            elif event.type == pg.KEYUP:
                self.keys = pg.key.get_pressed()
            elif event.type == pg.MOUSEBUTTONDOWN:
                self.mouse_pos = pg.mouse.get_pos()
                self.mouse_click[0], _, self.mouse_click[1] = pg.mouse.get_pressed()
                # self.mouse_click[0]表示左键，self.mouse_click[1]表示右键
                print(f"点击位置: ({self.mouse_pos[0]:3}, {self.mouse_pos[1]:3}) 左右键点击情况: {self.mouse_click}")

    # 状态转移
    def flip_state(self):  
        if self.state.next == c.EXIT:  
            pg.quit()  
            os._exit(0)  
        self.state_name = self.state.next  
        persist = self.state.cleanup()  
        self.state = self.state_dict[self.state_name]  
        # 传递数据库连接  
        if hasattr(self.state, 'db'):  
            self.state.db = self.db  
        self.state.startup(self.current_time, persist)

# 范围判断函数，用于判断点击
def inArea(rect:pg.Rect, x:int, y:int):
    if (rect.x <= x <= rect.right and
        rect.y <= y <= rect.bottom):
        return True
    else:
        return False

# 参数含义：原始图片，裁剪的x区域，裁剪的y区域，宽度，高度，颜色，缩放。
def get_image(  sheet:pg.Surface, x:int, y:int, width:int, height:int,
                colorkey:tuple[int]=c.BLACK, scale:int=1) -> pg.Surface:
    # 不保留alpha通道的图片导入
    image = pg.Surface([width, height])
    rect = image.get_rect()

    image.blit(sheet, (0, 0), (x, y, width, height))
    if colorkey:
        image.set_colorkey(colorkey)
    image = pg.transform.scale(image,
                                (int(rect.width*scale),
                                int(rect.height*scale)))
    return image

def get_image_alpha(sheet:pg.Surface, x:int, y:int, width:int, height:int,
                    colorkey:tuple[int]=c.BLACK, scale:int=1) -> pg.Surface:
    # 保留alpha通道的图片导入
    image = pg.Surface([width, height], SRCALPHA)
    rect = image.get_rect()

    image.blit(sheet, (0, 0), (x, y, width, height))
    image.set_colorkey(colorkey)
    image = pg.transform.scale(image,
                                (int(rect.width*scale),
                                int(rect.height*scale)))
    return image  
        
def load_image_frames(  directory:str, image_name:str,
                        colorkey:tuple[int], accept:tuple[str]) -> list[pg.Surface]:
    frame_list = []
    tmp = {}
    # image_name is "Peashooter", pic name is "Peashooter_1", get the index 1
    index_start = len(image_name) + 1 
    frame_num = 0
    for pic in os.listdir(directory):
        name, ext = os.path.splitext(pic)
        if ext.lower() in accept:
            index = int(name[index_start:])
            img = pg.image.load(os.path.join(directory, pic))
            if img.get_alpha():
                img = img.convert_alpha()
            else:
                img = img.convert()
                img.set_colorkey(colorkey)
            tmp[index]= img
            frame_num += 1

    for i in range(frame_num):  # 这里注意编号必须连续，否则会出错
        frame_list.append(tmp[i])
    return frame_list

# colorkeys 是设置图像中的某个颜色值为透明,这里用来消除白边
def load_all_gfx(   directory:str, colorkey:tuple[int]=c.WHITE,
                    accept:tuple[str]=(".png", ".jpg", ".bmp", ".gif", ".webp")) -> dict[str:pg.Surface]:
    graphics = {}
    for name1 in os.listdir(directory):
        # subfolders under the folder resources\graphics
        dir1 = os.path.join(directory, name1)
        if os.path.isdir(dir1):
            for name2 in os.listdir(dir1):
                dir2 = os.path.join(dir1, name2)
                if os.path.isdir(dir2):
                # e.g. subfolders under the folder resources\graphics\Zombies
                    for name3 in os.listdir(dir2):
                        dir3 = os.path.join(dir2, name3)
                        # e.g. subfolders or pics under the folder resources\graphics\Zombies\ConeheadZombie
                        if os.path.isdir(dir3):
                            # e.g. it"s the folder resources\graphics\Zombies\ConeheadZombie\ConeheadZombieAttack
                            image_name, _ = os.path.splitext(name3)
                            graphics[image_name] = load_image_frames(dir3, image_name, colorkey, accept)
                        else:
                            # e.g. pics under the folder resources\graphics\Plants\Peashooter
                            image_name, _ = os.path.splitext(name2)
                            graphics[image_name] = load_image_frames(dir2, image_name, colorkey, accept)
                            break
                else:
                # e.g. pics under the folder resources\graphics\Screen
                    name, ext = os.path.splitext(name2)
                    if ext.lower() in accept:
                        img = pg.image.load(dir2)
                        if img.get_alpha():
                            img = img.convert_alpha()
                        else:
                            img = img.convert()
                            img.set_colorkey(colorkey)
                        graphics[name] = img
    return graphics

SCREEN = pg.display.set_mode(c.SCREEN_SIZE) # 设置初始屏幕
GFX = load_all_gfx(c.PATH_IMG_DIR)
