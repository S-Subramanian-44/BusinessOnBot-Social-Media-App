from flask import Flask, request, render_template, redirect, session, jsonify
from werkzeug.utils import secure_filename
import os
import mysql.connector
import uuid  # For generating unique filenames

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Connect to MySQL
mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="mani@2133044",  # Replace with your MySQL password
    database="app"
)
mycursor = mydb.cursor()

# Define the upload folder and allowed extensions
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Function to check if the filename has an allowed extension
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to check if user is logged in
def is_logged_in():
    return 'username' in session

# Route for home page
@app.route('/')
def home():
    if is_logged_in():
        return redirect('/posts')
    else:
        return redirect('/login')

# Route for login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        mycursor.execute("SELECT * FROM Users WHERE Username = %s AND Password = %s", (username, password))
        user = mycursor.fetchone()
        if user:
            session['username'] = username
            return redirect('/posts')
        else:
            return render_template('login.html', error="Invalid username or password")
    else:
        return render_template('login.html')

# Route for registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        mycursor.execute("INSERT INTO Users (Username, Email, Password) VALUES (%s, %s, %s)", (username, email, password))
        mydb.commit()
        session['username'] = username
        return redirect('/posts')
    else:
        return render_template('register.html')

# Route for logging out
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/login')

# Route to handle profile photo update
@app.route('/update_profile_photo', methods=['POST'])
def update_profile_photo():
    if is_logged_in():
        username = session['username']
        if 'profile_photo' not in request.files:
            return redirect('/profile')
        file = request.files['profile_photo']
        if file.filename == '':
            return redirect('/profile')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + os.path.splitext(filename)[-1]  # Generate unique filename
            file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
            # Update the profile picture URL in the database
            profile_picture_url = os.path.join('static', 'uploads', unique_filename).replace('\\', '/')
            mycursor.execute("UPDATE Users SET ProfilePicture = %s WHERE Username = %s", (profile_picture_url, username))
            mydb.commit()
            return redirect('/profile')
    return "Unauthorized", 401

# Route for rendering the profile page
@app.route('/profile')
def profile():
    if is_logged_in():
        username = session['username']
        mycursor.execute("SELECT * FROM Users WHERE Username = %s", (username,))
        user = mycursor.fetchone()
        if user:
            email = user[2]
            created_at = user[5]
            profile_picture_url = user[4] if user[4] else '/static/profile.jpg'  # Default profile picture URL
            mycursor.execute("SELECT * FROM Posts WHERE UserID = (SELECT UserID FROM Users WHERE Username = %s)", (username,))
            user_posts = mycursor.fetchall()
            return render_template('profile.html', username=username, email=email, profile_picture_url=profile_picture_url, created_at=created_at, user_posts=user_posts)
        else:
            return "User not found"
    else:
        return redirect('/login')


@app.route('/create_post', methods=['POST'])
def create_post():
    if is_logged_in():
        username = session['username']
        post_content = request.form['post_content']
        if 'post_media' in request.files:
            file = request.files['post_media']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = str(uuid.uuid4()) + os.path.splitext(filename)[-1]  # Generate unique filename
                file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                # Construct the URL with correct format (replace backslashes with forward slashes)
                post_media_url = os.path.join('static', 'uploads', unique_filename).replace('\\', '/')
                mycursor.execute("INSERT INTO Posts (UserID, Content, MediaURL) VALUES ((SELECT UserID FROM Users WHERE Username = %s), %s, %s)", (username, post_content, post_media_url))
                mydb.commit()
                return redirect('/posts')
    return render_template('error.html', message="Unauthorized"), 401

# Route to toggle like on a post
@app.route('/toggle_like_post', methods=['POST'])
def toggle_like_post():
    if is_logged_in():
        data = request.get_json()
        post_id = data.get('postId')
        username = session['username']
        
        # Retrieve the user ID associated with the username
        mycursor.execute("SELECT UserID FROM Users WHERE Username = %s", (username,))
        user = mycursor.fetchone()
        if user:
            user_id = user[0]  # Extract the user ID from the result
            
            # Check if the user has already liked the post
            mycursor.execute("SELECT * FROM LIKES WHERE PostID = %s AND UserID = %s", (post_id, user_id))
            existing_like = mycursor.fetchone()
            if not existing_like:
                # Increment the like count in the Posts table
                mycursor.execute("UPDATE Posts SET Likes = Likes + 1 WHERE PostID = %s", (post_id,))
                mydb.commit()
                # Insert the like into the LIKES table
                mycursor.execute("INSERT INTO LIKES (UserID, PostID) VALUES (%s, %s)", (user_id, post_id))
                mydb.commit()
                return jsonify({"isLiked": True}), 200
            else:
                # Decrement the like count in the Posts table
                mycursor.execute("UPDATE Posts SET Likes = Likes - 1 WHERE PostID = %s", (post_id,))
                mydb.commit()
                # Delete the like from the LIKES table
                mycursor.execute("DELETE FROM LIKES WHERE PostID = %s AND UserID = %s", (post_id, user_id))
                mydb.commit()
                return jsonify({"isLiked": False}), 200
        else:
            return "User not found", 404
    else:
        return "Unauthorized", 401

@app.route('/get_likes/<int:post_id>', methods=['GET'])
def get_likes(post_id):
    try:
        # Execute the SQL query to fetch user IDs who liked the post
        mycursor.execute("SELECT UserID FROM LIKES WHERE PostID = %s", (post_id,))
        
        # Fetch all rows of the result
        likes = mycursor.fetchall()

        # Initialize a list to store usernames
        usernames = []

        # Iterate through each user ID and fetch the corresponding username
        for like in likes:
            user_id = like[0]
            mycursor.execute("SELECT Username FROM Users WHERE UserID = %s", (user_id,))
            username = mycursor.fetchone()[0]
            usernames.append(username)

        # Return the list of usernames
        return jsonify(usernames)
    except mysql.connector.Error as err:
        print("Error:", err)


@app.route('/get_username/<int:user_id>', methods=['GET'])
def get_username(user_id):
    try:
        # Execute the SQL query to fetch the username for the specified user_id
        mycursor.execute("SELECT Username FROM Users WHERE UserID = %s", (user_id,))
        
        # Fetch the username from the result
        username = mycursor.fetchone()[0]
        
        # Return the username
        return jsonify(username)
    except mysql.connector.Error as err:
        print("Error:", err)


# Route to handle post deletion
@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if is_logged_in():
        username = session['username']
        mycursor.execute("SELECT * FROM Posts WHERE PostID = %s AND UserID = (SELECT UserID FROM Users WHERE Username = %s)", (post_id, username))
        post = mycursor.fetchone()
        if post:
            mycursor.execute("DELETE FROM Posts WHERE PostID = %s", (post_id,))
            mydb.commit()
            return redirect('/profile')
        else:
            return render_template('error.html', message="Unauthorized action"), 403
    else:
        return redirect('/login')

# Route to view all posts
@app.route('/posts')
def view_posts():
    # Fetch posts with username from the users table
    mycursor.execute("SELECT Posts.*, Users.Username FROM Posts JOIN Users ON Posts.UserID = Users.UserID")
    posts = mycursor.fetchall()
    return render_template('posts.html', posts=posts)

if __name__ == '__main__':
    app.run(debug=True)
