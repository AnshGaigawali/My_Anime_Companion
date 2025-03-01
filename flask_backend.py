from flask import Flask, request, jsonify
import requests
import logging
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime
import difflib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
JIKAN_ANIME_URL = 'https://api.jikan.moe/v4/anime?q='
DB_CONNECTION_STRING = "mongodb+srv://anshgaigawali:anshtini@cluster2.l7iru.mongodb.net/animechatbot?retryWrites=true&w=majority&appName=Cluster2"
client = MongoClient(DB_CONNECTION_STRING)
db = client['animechatbot']

# Preprocess user input
def preprocess_input(user_input):
    anime_title = re.sub(r"(tell me about|info on|information about|let's talk about|give me details on|what can you say about|do you know about)?\s*", "", user_input, flags=re.IGNORECASE).strip()
    return anime_title

# Fetch anime info from Jikan API
def fetch_anime_info(anime_title):
    try:
        search_title = requests.utils.quote(anime_title)
        response = requests.get(f"{JIKAN_ANIME_URL}{search_title}")
        response.raise_for_status()
        response_data = response.json()
        
        if not response_data.get("data"):
            return f"I couldn't find any information on {anime_title}.", None, None

        closest_match = None
        highest_similarity = 0.0
        for anime in response_data["data"]:
            title = anime.get('title', 'Title not available')
            similarity = difflib.SequenceMatcher(None, anime_title.lower(), title.lower()).ratio()
            if similarity > highest_similarity:
                highest_similarity = similarity
                closest_match = anime

        if highest_similarity > 0.7:
            synopsis = closest_match.get('synopsis', 'Synopsis not available.')
            url = closest_match.get('url', '#')
            image_url = closest_match.get('images', {}).get('jpg', {}).get('image_url', None)
            trailer_url = closest_match.get('trailer', {}).get('url', None)
            response_text = f""" **Title:** {closest_match['title']} 
                                **Synopsis:** {synopsis} 
                                **Episodes:** {closest_match.get('episodes', 'N/A')} 
                                **Score:** {closest_match.get('score', 'N/A')} 
                                **Status:** {closest_match.get('status', 'N/A')} 
                                **More info:** [MyAnimeList]({url}) """
            return response_text.strip(), image_url, trailer_url
        
        return f"No exact match found for {anime_title}.", None, None

    except requests.RequestException as e:
        return f"An error occurred while fetching the anime data for {anime_title}.", None, None

# Fetch anime suggestions
def fetch_anime_suggestions(partial_input):
    try:
        search_title = requests.utils.quote(partial_input, safe='')
        response = requests.get(f"{JIKAN_ANIME_URL}{search_title}")
        logger.debug(f"API Request URL: {response.url}")
        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"Response Data: {response_data}")

        if not response_data.get('data'):
            logger.error(f"No data found for: {partial_input}")
            return []

        titles_set = set()
        for anime in response_data['data']:
            title = anime.get('title', 'Unknown Title')
            if title.lower() not in [item.lower() for item in titles_set]:
                titles_set.add(title)

        return list(titles_set)

    except requests.RequestException as e:
        logger.error(f"Error fetching suggestions: {e}")
        return []

# Fetch anime data with retry logic
def fetch_with_retry(url, max_retries=3, backoff_factor=0.5):
    for i in range(max_retries):
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if i == max_retries - 1:
                raise
            time.sleep(backoff_factor * (2 ** i))
    return None

# Analyze user history to detect preferences
def analyze_user_history(user_id):
    user_doc = db.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc or "history" not in user_doc:
        return {}

    history = user_doc["history"]
    genre_counter = {}
    total_episodes = 0
    total_anime = len(history)

    for item in history:
        try:
            response = requests.get(f"{JIKAN_ANIME_URL}{item['user_input']}")
            response.raise_for_status()
            response_data = response.json().get('data', [])
            for anime in response_data:
                # Count genres
                for genre in anime.get("genres", []):
                    genre_name = genre['name']
                    genre_counter[genre_name] = genre_counter.get(genre_name, 0) + 1

                # Safely handle episodes (default to 0 if None)
                episodes = anime.get("episodes", 0) or 0  # Treat None as 0
                total_episodes += episodes
        except requests.RequestException as e:
            logger.error(f"Error fetching anime data for {item['user_input']}: {e}")
            continue

    avg_episodes = total_episodes / total_anime if total_anime > 0 else 0
    sorted_genres = sorted(genre_counter.items(), key=lambda x: x[1], reverse=True)
    top_genres = [genre[0] for genre in sorted_genres[:3]]

    return {
        "top_genres": top_genres,
        "avg_episodes": avg_episodes
    }
# Chat endpoint
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No input data provided'}), 400

        user_input = data.get('input')
        user_id = data.get('user_id', None)
        response_text, image_url, trailer_url = fetch_anime_info(user_input)

        if user_id:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$push": {"history": {
                    "user_input": data['input'],
                    "response": response_text,
                    "timestamp": timestamp,
                    "image_url": image_url,
                    "trailer_url": trailer_url
                }}}
            )

        return jsonify({'response': response_text, 'image_url': image_url, 'trailer_url': trailer_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Search assistance endpoint
@app.route('/search-assistance', methods=['POST'])
def search_assistance():
    try:
        data = request.get_json()
        user_input = data['input'].strip()
        suggestions = fetch_anime_suggestions(user_input)
        logger.debug(f"Suggestions provided: {suggestions}")
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        logger.error(f"Exception in search assistance: {e}")
        return jsonify({'error': str(e)}), 500

# Recommendation endpoint (without caching)
@app.route('/recommend_based_on_history', methods=['POST'])
def recommend_based_on_history():
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        # Fetch user's search history
        user_doc = db.users.find_one({"_id": ObjectId(user_id)})
        if not user_doc or "history" not in user_doc or not user_doc["history"]:
            logger.info(f"No history found for user {user_id}. Falling back to trending anime.")
            try:
                response = requests.get("https://api.jikan.moe/v4/top/anime")
                response.raise_for_status()
                trending_data = response.json().get("data", [])
                recommendations = [{
                    "title": anime.get("title", "Title not available"),
                    "score": anime.get("score", "N/A"),
                    "synopsis": anime.get("synopsis", "Synopsis not available."),
                    "image_url": anime.get("images", {}).get("jpg", {}).get("image_url", None),
                    "url": anime.get("url", "#"),
                    "genres": [genre['name'] for genre in anime.get("genres", [])]
                } for anime in trending_data[:10]]  # Limit to top 10
                return jsonify(recommendations)
            except requests.RequestException as e:
                logger.error(f"Error fetching trending anime: {e}")
                return jsonify({"error": "Failed to fetch trending anime"}), 500

        # If history exists, fetch recommendations based on history
        anime_titles = [item['user_input'] for item in user_doc["history"]]
        logger.info(f"User history titles: {anime_titles}")
        seen_titles = set()
        recommendations = []

        # Analyze user history for preferences
        user_analysis = analyze_user_history(user_id)
        top_genres = user_analysis.get("top_genres", [])
        avg_episodes = user_analysis.get("avg_episodes", 0)
        logger.info(f"Top genres: {top_genres}, Avg episodes: {avg_episodes}")

        # Fetch recommendations in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_title = {executor.submit(fetch_with_retry, f"{JIKAN_ANIME_URL}{title}"): title for title in anime_titles if title not in seen_titles}
            for future in as_completed(future_to_title):
                title = future_to_title[future]
                try:
                    data = future.result()
                    logger.debug(f"API response for '{title}': {data}")
                    if not data.get('data'):
                        logger.warning(f"No data found for '{title}'.")
                        continue

                    for anime in data.get('data', []):
                        # Filter based on user preferences
                        if top_genres and not any(genre['name'] in top_genres for genre in anime.get("genres", [])):
                            logger.debug(f"Skipping '{anime.get('title')}' due to genre mismatch.")
                            continue
                        if avg_episodes > 0 and anime.get("episodes", 0) > avg_episodes * 1.5:
                            logger.debug(f"Skipping '{anime.get('title')}' due to episode count mismatch.")
                            continue

                        recommendations.append({
                            "title": anime.get("title", "Title not available"),
                            "score": anime.get("score", "N/A"),
                            "synopsis": anime.get("synopsis", "Synopsis not available."),
                            "image_url": anime.get("images", {}).get("jpg", {}).get("image_url", None),
                            "url": anime.get("url", "#"),
                            "genres": [genre['name'] for genre in anime.get("genres", [])]
                        })
                except Exception as e:
                    logger.error(f"Error processing anime data for {title}: {e}")

        # Sort and limit recommendations
        recommendations.sort(key=lambda x: x.get("score", 0) or 0, reverse=True)
        recommendations = recommendations[:10]
        logger.info(f"Generated recommendations: {recommendations}")

        # If no recommendations are found, fallback to trending anime
        if not recommendations:
            logger.warning("No recommendations found. Falling back to trending anime.")
            try:
                response = requests.get("https://api.jikan.moe/v4/top/anime")
                response.raise_for_status()
                trending_data = response.json().get("data", [])
                recommendations = [{
                    "title": anime.get("title", "Title not available"),
                    "score": anime.get("score", "N/A"),
                    "synopsis": anime.get("synopsis", "Synopsis not available."),
                    "image_url": anime.get("images", {}).get("jpg", {}).get("image_url", None),
                    "url": anime.get("url", "#"),
                    "genres": [genre['name'] for genre in anime.get("genres", [])]
                } for anime in trending_data[:10]]  # Limit to top 10
            except requests.RequestException as e:
                logger.error(f"Error fetching trending anime: {e}")
                return jsonify({"error": "Failed to fetch trending anime"}), 500

        return jsonify(recommendations)
    except Exception as e:
        logger.error(f"Error in recommendation based on history endpoint: {e}")
        return jsonify({'error': str(e)}), 500

# Feedback endpoint
@app.route('/feedback', methods=['POST'])
def feedback():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        anime_title = data.get('anime_title')
        feedback_type = data.get('feedback')  # e.g., 'like', 'dislike'

        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$push": {"feedback": {
                "anime_title": anime_title,
                "feedback": feedback_type,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }}}
        )
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error in feedback endpoint: {e}")
        return jsonify({'error': str(e)}), 500

# Trending endpoint
@app.route('/trending')
def trending():
    try:
        response = requests.get("https://api.jikan.moe/v4/top/anime")
        response.raise_for_status()
        trending_data = response.json()

        trending_anime = []
        for anime in trending_data.get("data", []):
            trending_anime.append({
                "title": anime.get("title", "Title not available"),
                "score": anime.get("score", "N/A"),
                "synopsis": anime.get("synopsis", "Synopsis not available."),
                "image_url": anime.get("images", {}).get("jpg", {}).get("image_url", None),
                "url": anime.get("url", "#")
            })

        return jsonify(trending_anime)
    except requests.RequestException as e:
        logger.error(f"Error fetching trending anime: {e}")
        return jsonify({"error": "Failed to fetch trending anime"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)