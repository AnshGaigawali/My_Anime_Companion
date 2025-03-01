import os
import re
import json
import streamlit as st
import requests
from pymongo import MongoClient
import bcrypt
import logging
import datetime
from bson.objectid import ObjectId
from functools import lru_cache

# Custom CSS for modern design
def apply_css(theme_mode):
    if theme_mode == "Dark Mode":
        css_file = "dark_mode.css"
    else:
        css_file = "light_mode.css"
    
    with open(css_file) as f:
        css_content = f.read()
        st.markdown(f'<style>{css_content}</style>', unsafe_allow_html=True)

# Preprocess user input
def preprocess_input(user_input):
    anime_title = re.sub(r"(tell me about|info on|information about|let's talk about|give me details on|what can you say about|do you know about)?\s*", "", user_input, flags=re.IGNORECASE).strip()
    anime_title = re.sub(r"[^\w\s]", "", anime_title).strip()
    return anime_title

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
FLASK_API_URL = "https://myanimecompanion-feh1.onrender.com"
DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING", "mongodb+srv://anshgaigawali:anshtini@cluster2.l7iru.mongodb.net/animechatbot?retryWrites=true&w=majority&appName=Cluster2")
client = MongoClient(DB_CONNECTION_STRING)
db = client['animechatbot']
users_collection = db['users']
ratings_collection = db["ratings"]
community_collection = db["community"]

# Display trending anime
def display_trending_anime():
    try:
        response = requests.get(f"{FLASK_API_URL}/trending")
        response.raise_for_status()
        trending_anime = response.json()
        if trending_anime:
            st.header("Trending Anime")
            for anime in trending_anime:
                st.write(f"**Title:** {anime['title']}")
                st.write(f"**Score:** {anime.get('score', 'N/A')}")
                st.write(f"**Synopsis:** {anime.get('synopsis', 'No synopsis available.')}")
                st.markdown("---")
        else:
            st.warning("No trending anime found.")
    except requests.RequestException as e:
        logger.error(f"Error fetching trending anime: {e}")
        st.error("Failed to fetch trending anime. Please try again later.")

# Display recommendations
def get_recommendations(user_id):
    try:
        response = requests.post(f"{FLASK_API_URL}/recommend_based_on_history", json={"user_id": user_id})
        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Recommendations data: {response_data}")  # Debug log
        return response_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching recommendations: {e}")
        st.error("Failed to fetch recommendations. Please try again later.")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response: {e}")
        st.error("Invalid data received. Please try again later.")
        return []

def display_recommendations(recommendations):
    st.header("Your Anime Recommendations")
    if isinstance(recommendations, list):
        if not recommendations:
            st.warning("No recommendations found. Try searching for some anime first!")
        else:
            for rec in recommendations:
                if isinstance(rec, dict) and 'title' in rec:
                    st.write(f"**Title:** {rec['title']}")
                    st.write(f"**Score:** {rec.get('score', 'N/A')}")
                    st.write(f"**Synopsis:** {rec.get('synopsis', 'No synopsis available.')}")
                    if rec.get("image_url"):
                        st.image(rec["image_url"], caption=rec["title"], width=300)
                    st.markdown("---")
                else:
                    st.error("Unexpected recommendation format. Please check the backend response.")
    else:
        st.error("Invalid recommendations data. Please check the backend response.")

# User authentication functions
def signup(email, password):
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        st.error("Please enter a valid email address.")
        return
    if len(password) < 8:
        st.error("Password must be at least 8 characters long.")
        return
    if users_collection.find_one({"email": email}):
        st.error("Email already exists. Please log in.")
        return
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    user = {"email": email, "password": hashed_password, "preferences": {}}
    result = users_collection.insert_one(user)
    logger.info(f"User inserted with id: {result.inserted_id}")
    st.success(f"Account created for {email}")

def login(email, password):
    user = users_collection.find_one({"email": email})
    if user and bcrypt.checkpw(password.encode('utf-8'), user["password"]):
        st.success(f"Logged in as {email}. Please refresh the page.")
        st.session_state["user_id"] = str(user["_id"])
        st.session_state["user_email"] = email
        st.session_state["login_success"] = True
        return str(user["_id"])
    st.error("Invalid credentials")
    return None

def logout():
    st.session_state["user_id"] = None
    st.session_state["user_email"] = None
    st.session_state["logout_success"] = True
    st.success("You have been logged out successfully. Please refresh the page.")

def delete_account(user_id):
    try:
        # Delete the user's account from the users collection
        user_delete_result = users_collection.delete_one({"_id": ObjectId(user_id)})
        
        # Delete all community posts by the user
        community_delete_result = community_collection.delete_many({"user_id": user_id})
        
        if user_delete_result.deleted_count > 0:
            st.success("Account and associated data deleted successfully.")
            st.session_state["account_deleted"] = True
        else:
            st.error("Failed to delete the account. Please try again.")
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        st.error("An error occurred while deleting the account.")

# Chatbot and recommendation functions
def companion_response(input_text, user_id=None, is_suggestion=False):
    preprocessed_text = input_text if is_suggestion else preprocess_input(input_text)
    response = requests.post(f"{FLASK_API_URL}/chat", json={"input": preprocessed_text, "user_id": user_id})
    response_json = response.json()
    response_text = response_json.get('response', "I'm sorry, I couldn't find any information.")
    image_url = response_json.get('image_url')
    trailer_url = response_json.get('trailer_url')
    return response_text, image_url, trailer_url

def search_assistance(input_text):
    try:
        response = requests.post(f"{FLASK_API_URL}/search-assistance", json={"input": input_text})
        response.raise_for_status()
        logger.debug(f"API Response: {response.text}")
        response_data = response.json()
        return response_data.get('suggestions', [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching suggestions: {e}")
        st.error("Failed to fetch suggestions. Please try again later.")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response: {e}")
        st.error("Invalid data received. Please try again later.")
        return []

# Display anime information
def display_anime_info(response_text, image_url=None, trailer_url=None):
    anime_title_match = re.search(r'<h2><strong>Title:</strong></h2>(.*?)<br>', response_text)
    anime_title = anime_title_match.group(1).strip() if anime_title_match else "Anime Character"
    
    formatted_response = response_text.replace("**Title:**", "<h2><strong>Title:</strong></h2>")
    formatted_response = formatted_response.replace("**Episodes:**", "<h3><strong>Episodes:</strong></h3>")
    formatted_response = formatted_response.replace("**Score:**", "<h3><strong>Score:</strong></h3>")
    formatted_response = formatted_response.replace("**Status:**", "<h3><strong>Status:</strong></h3>")
    formatted_response = formatted_response.replace("**Synopsis:**", "<h3><strong>Synopsis:</strong></h3>")
    
    formatted_response = formatted_response.replace("\n", "<br>")
    formatted_response = re.sub(r'(http[s]?://\S+)', r'<a href="\1" target="_blank">Click Here for More Info</a>)', formatted_response)
    
    html_response = f"""
    <div style='text-align: left; font-family: Arial, sans-serif; line-height: 1.5; margin-bottom:20px;' class='fade-in'>
        {formatted_response}
    </div>
    """
    st.markdown(html_response, unsafe_allow_html=True)
    
    if image_url:
        st.markdown(f"<div style='text-align: center;'><img src='{image_url}' alt='{anime_title}' style='max-width: 100%; height: auto; margin-bottom: 20px;' class='fade-in' /></div>", unsafe_allow_html=True)
        
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    if trailer_url:
        st.video(trailer_url, format="video/mp4", start_time=0)

# Community section
def add_community_post(user_id, post):
    if not post.strip():
        st.error("Post cannot be empty.")
        return
    community_collection.insert_one({
        "user_id": user_id,
        "post": post,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    st.success("Your post has been added to the community. Please refresh the page.")

def delete_community_post(post_id):
    community_collection.delete_one({"_id": ObjectId(post_id)})
    st.success("Post deleted successfully! Please refresh the page.")

def display_community_posts(user_id):
    posts = community_collection.find().sort("timestamp", -1)
    if posts:
        st.header("Community Posts")
        for post in posts:
            st.write(f"**User:** {post['user_id']}")
            st.write(f"**Post:** {post['post']}")
            st.write(f"**Timestamp:** {post['timestamp']}")
            if post["user_id"] == user_id:
                if st.button(f"Delete Post (ID: {post['_id']})", key=f"delete_post_{post['_id']}"):
                    delete_community_post(post["_id"])
                    st.query_params = {}  # Refresh the page to reflect the changes
            st.markdown("---")
    else:
        st.warning("No posts found in the community.")

# Profile section
def profile_page():
    st.header("User Profile")
    st.write("Here you can update your profile information.")
    user_doc = users_collection.find_one({"_id": ObjectId(st.session_state["user_id"])})
    if user_doc:
        email = user_doc.get("email", "")
        name = user_doc.get("name", "")

        # Disabled email input field
        st.text_input("Email", value=email, disabled=True)

        # Update name
        new_name = st.text_input("Name", value=name)

        # Update password
        new_password = st.text_input("New Password", type='password')

        # Update profile button
        if st.button("Update Profile", key="update_profile"):
            update_fields = {}
            if new_name != name:
                update_fields["name"] = new_name
            if new_password:
                if len(new_password) < 8:
                    st.error("Password must be at least 8 characters long.")
                else:
                    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                    update_fields["password"] = hashed_password
            if update_fields:
                users_collection.update_one({"_id": ObjectId(st.session_state["user_id"])}, {"$set": update_fields})
                st.success("Profile updated successfully. Please refresh the page.")
            else:
                st.warning("No changes detected.")

        # Delete account section
        st.markdown("---")  # Add a separator
        st.subheader("Delete Account")
        st.warning("This action is irreversible. All your data, including your profile, conversation history, and community posts, will be permanently deleted.")

        # Confirmation dialog for account deletion
        if st.checkbox("I understand the consequences and want to delete my account."):
            if st.button("Delete My Account", key="delete_account"):
                # Delete the user's account
                delete_account(st.session_state["user_id"])
                st.session_state["user_id"] = None  # Clear the session state
                st.session_state["user_email"] = None
                st.session_state["account_deleted"] = True
                st.query_params = {}  # Refresh the page
    else:
        st.warning("User not found.")

def delete_account(user_id):
    try:
        # Delete the user's account from the database
        result = users_collection.delete_one({"_id": ObjectId(user_id)})
        if result.deleted_count > 0:
            st.success("Account deleted successfully. Please refresh the page.")
            st.session_state["account_deleted"] = True
        else:
            st.error("Failed to delete the account. Please try again.")
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        st.error("An error occurred while deleting the account.")

# Conversation history
def save_conversation_history(user_id, user_input, response):
    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$push": {"history": {"user_input": user_input, "response": response, "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}},
        upsert=True
    )

def delete_conversation_history(user_id):
    try:
        users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"history": []}}  # Clear the history array
        )
        st.success("Conversation history deleted successfully! Please refresh the page.")
    except Exception as e:
        logger.error(f"Error deleting conversation history: {e}")
        st.error("An error occurred while deleting the conversation history.")

def display_conversation_history(user_id):
    user_doc = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_doc and "history" in user_doc and user_doc["history"]:
        st.header("Conversation History")
        if st.button("Delete Conversation History", key="delete_conversation_history"):
            delete_conversation_history(user_id)
            st.query_params = {}  # Refresh the page
        for history in user_doc["history"]:
            st.text(f"User: {history['user_input']}\nMyAnimeCompanion: {history['response']}\nTimestamp: {history['timestamp']}")
            st.markdown("---")
    else:
        st.warning("No conversation history found for this user.")

def main():
    st.set_page_config(page_title="MyAnimeCompanion", page_icon="🎬", layout="wide")

    # Initialize session state for theme mode and navigation
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = "Light Mode"  # Default theme
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Home"  # Default page

    # Apply the selected theme
    apply_css(st.session_state["theme_mode"])

    # Sidebar for navigation
    with st.sidebar:
        st.title("Navigation Menu")

        # Navigation menu
        #st.sidebar.title("Navigation")
        menu = ["Home", "Profile", "Community", "Trending", "Recommendations", "Conversation History", "About"]
        choice = st.sidebar.selectbox("Menu", menu)

    
    # Main layout for title, refresh button, and theme toggle
    col1, col2, col3 = st.columns([0.6, 0.1, 0.1])  # Adjust the ratio as needed

    # Place the heading in the first column
    with col1:
        st.title("🎬 MyAnimeCompanion")

    # Place the refresh button in the second column
    with col2:
        if st.button("Refresh", key="refresh_button"):
            st.query_params = {}  # Refresh the page
    
    # Place the theme toggle button in the third column
    with col3:
        # Toggle button for dark/light mode
        if st.button(f"🌙" if st.session_state["theme_mode"] == "Dark Mode" else f"☀️"):
            st.session_state["theme_mode"] = "Dark Mode" if st.session_state["theme_mode"] == "Light Mode" else "Light Mode"
            st.query_params = {}  # Refresh the page to apply the new theme

    # Initialize session state for user authentication
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = None
        st.session_state["user_email"] = None
        st.session_state["login_success"] = False
        st.session_state["logout_success"] = False
        st.session_state["account_deleted"] = False

    if st.session_state.get("account_deleted", False):
        st.session_state["account_deleted"] = False  # Reset the flag
        st.session_state["current_page"] = "Home"  # Redirect to home page
        st.query_params = {}  # Refresh the page
    
    # Page logic based on navigation choice
    if choice == "Home":
        if st.session_state["user_id"]:
            user_doc = users_collection.find_one({"_id": ObjectId(st.session_state["user_id"])})
            name = user_doc.get("name", "")
            greeting_name = name if name else st.session_state["user_email"]
            
            st.header(f"Welcome {greeting_name}!")
            st.write("Search for your favorite anime.")

            # Search and recommendations
            user_input = st.text_input("Search for an anime:")
            suggestions = search_assistance(user_input)
            selected_anime = st.selectbox("Top Results:", options=suggestions)
            if st.button("Search", key="search_anime"):
                with st.spinner('Fetching anime information...'):
                    if selected_anime:
                        response_text, image_url, trailer_url = companion_response(selected_anime, st.session_state["user_id"], is_suggestion=True)
                        display_anime_info(response_text, image_url, trailer_url)
                    else:
                        st.warning("Please enter an anime name to get suggestions.")

            # Logout button
            if st.button("Logout", key="logout"):
                logout()
                st.session_state["logout_success"] = True
                st.query_params = {}  # Refresh the page after logout

        else:
            st.header("Authentication")
            auth_mode = st.radio("Choose an option", ["Sign In", "Sign Up"])

            if auth_mode == "Sign In":
                with st.form(key='sign_in_form'):
                    email = st.text_input("Email")
                    password = st.text_input("Password", type='password')
                    submit_button = st.form_submit_button(label='Sign In')

                    if submit_button:
                        user_id = login(email, password)
                        if user_id:
                            st.session_state["user_id"] = user_id
                            st.query_params = {}  # Refresh the page after sign-in

            elif auth_mode == "Sign Up":
                with st.form(key='sign_up_form'):
                    email = st.text_input("Email")
                    password = st.text_input("Password", type='password')
                    submit_button = st.form_submit_button(label='Sign Up')

                    if submit_button:
                        signup(email, password)
                        st.session_state["user_email"] = email
                        st.query_params = {}  # Refresh the page after sign-up

    elif choice == "Community":
        if st.session_state["user_id"]:
            st.header("Community")
            st.subheader("Write your post:")
            post = st.text_area("")
            if st.button("Submit Post", key="submit_post"):
                add_community_post(st.session_state["user_id"], post)
            display_community_posts(st.session_state["user_id"])
        else:
            st.warning("You need to log in to participate in the community.")

    elif choice == "Trending":
        display_trending_anime()

    elif choice == "Recommendations":
        if st.session_state["user_id"]:
            with st.spinner('Fetching recommendations...'):
                recommendations = get_recommendations(st.session_state["user_id"])
                display_recommendations(recommendations)
        else:
            st.warning("You need to log in to view your recommendations.")

    elif choice == "Conversation History":
        if st.session_state["user_id"]:
            display_conversation_history(st.session_state["user_id"])
        else:
            st.warning("You need to log in to view your conversation history.")

    elif choice == "Profile":
        if st.session_state["user_id"]:
            profile_page()
        else:
            st.warning("You need to log in to view your profile.")

    elif choice == "About":
        st.header("About MyAnimeCompanion")
        st.write("""
        Welcome to **MyAnimeCompanion**, your personal assistant for all things anime! This project is designed to help anime enthusiasts explore, discover, and learn more about their favorite anime series and characters.
        """)

        st.subheader("Overview")
        st.write("""
        **MyAnimeCompanion** is an interactive application that helps you search for anime, get personalized recommendations, and connect with other anime fans. Whether you're looking for details about a specific anime or want to discover trending shows, this companion has got you covered!
        """)

        st.subheader("Features")
        st.write("""
        - **Search for Anime**: Get detailed information about any anime, including title, synopsis, episodes, score, and more.
        - **Trending Anime**: Discover the most popular anime currently trending.
        - **Personalized Recommendations**: Receive anime recommendations based on your search history and preferences.
        - **Community Interaction**: Share your thoughts and interact with other anime fans in the community section.
        - **Conversation History**: Keep track of your previous interactions with the companion.
        - **User Profiles**: Update your profile information and preferences.
        - **Dark/Light Mode**: Choose a theme that suits your preference.
        - **Delete Account**: Delete your account along with the conversation history and community posts.
        """)

        st.subheader("How It Works")
        st.write("""
        1. **User Input**: You can ask the companion about any anime by typing the name of the anime (e.g., "Attack on Titan").
        2. **Backend Processing**: The companion fetches relevant data from the **Jikan API**.
        3. **Response Generation**: The companion provides a detailed response, including information about the anime, an image, and a trailer (if available).
        4. **Database Integration**: Your interactions are stored in a **MongoDB** database to provide personalized recommendations and maintain conversation history.
        """)

        st.subheader("Technologies Used")
        st.write("""
        - **Frontend**: Streamlit (for building the user interface)
        - **Backend**: Flask (for handling API requests and processing)
        - **Database**: MongoDB (for storing user data and conversation history)
        - **APIs**: Jikan API (for fetching anime data)
        - **Authentication**: bcrypt (for secure user authentication)
        - **Deployment**: Render (for production deployment)
        """)

        st.subheader("Purpose")
        st.write("""
        The purpose of this project is to provide anime fans with a seamless and interactive way to explore their favorite anime. Whether you're a casual viewer or a hardcore fan, **MyAnimeCompanion** is here to enhance your anime experience!
        """)

        st.subheader("Additional Information")
        st.write("""
        - **Developer**: Ansh Gaigawali
        - **GitHub Repository**: https://github.com/AnshGaigawali
        - **Contact**: ansh.gaigawali22@pccoepune.org
        """)

        st.write("Feel free to explore and ask about different anime titles!")

if __name__ == '__main__':
    main()
