# 数据库操作脚本。
# # 列出所有表  
# python db.py --list-tables  

# # 显示表结构  
# python db.py --schema level_progress  

# # 查询表中的所有数据  
# python db.py --query level_progress  

# # 更新表中的值（最新记录）  
# python db.py --update level_progress level_num 5  

# # 使用条件更新特定记录  
# python db.py --update level_progress level_num 5 --condition "id=1"

import os  
import sqlite3  
import argparse  

# 获取数据库路径 - 根据您的设置修改  
if os.name == "nt":  
    DB_PATH = os.path.expandvars(os.path.join("%APPDATA%", "pypvz", "userdata.db"))  
else:  
    DB_PATH = os.path.expanduser(os.path.join("~", ".config", "pypvz", "userdata.db"))  

def connect_db():  
    """连接到数据库"""  
    conn = sqlite3.connect(DB_PATH)  
    conn.row_factory = sqlite3.Row  # 允许通过列名访问结果  
    return conn  

def list_tables(conn):  
    """列出所有表"""  
    cursor = conn.cursor()  
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")  
    tables = cursor.fetchall()  
    print("数据库中的表:")  
    for table in tables:  
        print(f"- {table['name']}")  

def show_schema(conn, table_name):  
    """显示表结构"""  
    cursor = conn.cursor()  
    cursor.execute(f"PRAGMA table_info({table_name});")  
    columns = cursor.fetchall()  
    print(f"\n表 '{table_name}' 的结构:")  
    for col in columns:  
        print(f"- {col['name']} ({col['type']})")  

def query_table(conn, table_name):  
    """查询表中的所有数据"""  
    cursor = conn.cursor()  
    cursor.execute(f"SELECT * FROM {table_name};")  
    rows = cursor.fetchall()  
    
    if not rows:  
        print(f"表 '{table_name}' 中没有数据")  
        return  
    
    print(f"\n表 '{table_name}' 中的数据:")  
    cols = [column[0] for column in cursor.description]  
    print(" | ".join(cols))  
    print("-" * (sum(len(c) for c in cols) + 3 * (len(cols) - 1)))  
    
    for row in rows:  
        row_data = [str(row[col]) for col in cols]  
        print(" | ".join(row_data))  

def update_value(conn, table_name, column_name, value, condition=None):  
    """更新表中的值"""  
    cursor = conn.cursor()  
    
    if condition:  
        query = f"UPDATE {table_name} SET {column_name} = ? WHERE {condition}"  
    else:  
        # 默认更新最后一条记录  
        query = f"UPDATE {table_name} SET {column_name} = ? WHERE id = (SELECT MAX(id) FROM {table_name})"  
    
    try:  
        # 尝试将值转换为适当的类型  
        try:  
            value = int(value)  
        except ValueError:  
            try:  
                value = float(value)  
            except ValueError:  
                pass  # 保持为字符串  
                
        cursor.execute(query, (value,))  
        conn.commit()  
        print(f"已将表 '{table_name}' 中的列 '{column_name}' 更新为 '{value}'")  
    except sqlite3.Error as e:  
        print(f"更新失败: {e}")  

def main():  
    parser = argparse.ArgumentParser(description='SQLite 数据库管理工具')  
    parser.add_argument('--list-tables', action='store_true', help='列出所有表')  
    parser.add_argument('--schema', metavar='TABLE', help='显示指定表的结构')  
    parser.add_argument('--query', metavar='TABLE', help='查询指定表中的所有数据')  
    parser.add_argument('--update', nargs=3, metavar=('TABLE', 'COLUMN', 'VALUE'),   
                        help='更新表中的值 (例如: --update level_progress level_num 5)')  
    parser.add_argument('--condition', help='更新时的条件 (例如: "id=1")')  
    
    args = parser.parse_args()  
    
    conn = connect_db()  
    
    try:  
        if args.list_tables:  
            list_tables(conn)  
        
        if args.schema:  
            show_schema(conn, args.schema)  
        
        if args.query:  
            query_table(conn, args.query)  
        
        if args.update:  
            update_value(conn, args.update[0], args.update[1], args.update[2], args.condition)  
            
        if not any([args.list_tables, args.schema, args.query, args.update]):  
            # 如果没有指定任何操作，显示帮助  
            parser.print_help()  
    finally:  
        conn.close()  

if __name__ == '__main__':  
    main()