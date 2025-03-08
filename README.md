<h1 align="center" id="title">MyAnimeCompanion</h1>

<p align="center"><img src="https://socialify.git.ci/AnshGaigawali/My_Anime_Companion/image?font=Inter&amp;language=1&amp;name=1&amp;owner=1&amp;pattern=Charlie+Brown&amp;stargazers=1&amp;theme=Auto" alt="project-image"></p>

<p id="description">MyAnimeCompanion is an interactive web application designed for anime enthusiasts to explore their favorite anime get personalized recommendations and connect with other fans. Whether you're searching for details about a specific anime discovering trending shows or sharing your thoughts in the community this app has got you covered!</p>

<h2>🧐 Features</h2>

Here're some of the project's best features:

*   Search for Anime: Get detailed information about any anime, including title, synopsis, episodes, score, and more.
*   Trending Anime: Discover the most popular anime currently trending.
*   Community Interaction: Share your thoughts and interact with other anime fans in the community section.
*   Conversation History: Keep track of your previous interactions with the companion.
*   User Profiles: Update your profile information.
*   Dark/Light Mode: Choose a theme that suits your preference.
*   Delete Account: Delete your account along with the conversation history and community posts.


<h2>🛠️ Installation Steps:</h2>

<p>1. Clone the Repository</p>

```
git clone https://github.com/your-username/MyAnimeCompanion.git
cd MyAnimeCompanion
```

<p>2. Set Up a Virtual Environment</p>

```
python -m venv venv
source venv/bin/activate 
```

<p>3. Install Dependencies</p>

```
pip install -r requirements.txt
```

<p>4. Set Up Environment Variables</p>

```
DB_CONNECTION_STRING=your_mongodb_connection_string
```

<p>5. Run the Backend Server</p>

```
python backend/app.py
```

<p>6. Run the Frontend Server</p>

```
streamlit run frontend/app.py
```

<h2>🍰 Contribution Guidelines:</h2>

We welcome contributions from the community to improve MyAnimeCompanion. Whether it's fixing bugs adding new features or improving documentation your input is highly valued. To contribute fork the repository create a new branch make your changes and submit a pull request. If you encounter any issues or have suggestions feel free to open an issue in the repository. Together we can enhance this chatbot and make it even better for anime enthusiasts! 🚀

<h2>💻 Built with</h2>

Technologies used in the project:

*   Frontend: Streamlit (for chatbot UI)
*   Backend: Flask
*   Database: MongoDB
*   APIs: Jikan API (for anime data)
*   Authentication: bcrypt
*   Deployment: Render (or your preferred platform)

<h2> Acknowledgments</h2>

*   Thanks to the Jikan API for providing anime data.
*   Special thanks to the open-source community for their invaluable tools and libraries.
