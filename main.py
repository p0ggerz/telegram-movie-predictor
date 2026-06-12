import asyncio
import random

import pandas as pd
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, KeyboardButton, Message,
                           ReplyKeyboardMarkup)

from emotion_analyzer import EMOTION_GENRES, analyze_emotion


class ComboSearch(StatesGroup):
    waiting_genre = State()
    waiting_year = State()
    waiting_country = State()


class EmotionSearch(StatesGroup):
    waiting_text = State()


df = pd.read_csv("kinopoisk_top250_cleaned.csv")
movies = df.to_dict('records')
print(f"Загружено фильмов: {len(movies)}")


YEAR_RANGES = [
    {"name": "1920-1929", "start": 1920, "end": 1929},
    {"name": "1930-1939", "start": 1930, "end": 1939},
    {"name": "1940-1949", "start": 1940, "end": 1949},
    {"name": "1950-1959", "start": 1950, "end": 1959},
    {"name": "1960-1969", "start": 1960, "end": 1969},
    {"name": "1970-1979", "start": 1970, "end": 1979},
    {"name": "1980-1989", "start": 1980, "end": 1989},
    {"name": "1990-1999", "start": 1990, "end": 1999},
    {"name": "2000-2009", "start": 2000, "end": 2009},
    {"name": "2010-2019", "start": 2010, "end": 2019}
]


def get_all_genres():
    genres = set()
    for m in movies:
      for g in str(m['Genres_normalized']).split(', '):
        genre = g.strip()
        if genre:
          genres.add(genre)
    return sorted(genres)


def get_all_countries():
    countries = set()
    for m in movies:
      for c in str(m['country']).split(','):
        country = c.strip()
        if country:
          countries.add(country)
    return sorted(countries)


def get_available_years_for_genre(genre=None):
    years = set()
    for m in movies:
        if genre:
            genres_list = [g.strip() for g in str(m['Genres_normalized']).split(', ')]
            if genre not in genres_list:
                continue
        if m['year']:
            decade = (m['year'] // 10) * 10
            years.add(decade)
    return sorted(years, reverse=True)


def get_available_countries_for_filters(genre=None, year_range=None):
    countries = set()
    for m in movies:
        if genre:
            genres_list = [g.strip() for g in str(m['Genres_normalized']).split(', ')]
            if genre not in genres_list:
                continue
        if year_range and m['year']:
            if not (year_range['start'] <= m['year'] <= year_range['end']):
                continue
        for c in str(m['country']).split(','):
            country = c.strip()
            if country:
                countries.add(country)
    return sorted(countries)


def get_filtered_movies(genre=None, year_range=None, country=None, n=5):
    result = []
    for m in movies:
        if genre:
            genres_list = [g.strip() for g in str(m['Genres_normalized']).split(', ')]
            if genre not in genres_list:
                continue
        if year_range and m['year']:
            if not (year_range['start'] <= m['year'] <= year_range['end']):
                continue
        if country:
            if country.lower() not in str(m['country']).lower():
                continue
        result.append(m)
    random.shuffle(result)
    return result[:n]


def get_decade_name(year):
    return f"{year}-{year+9}"


def find_by_genre(genre, n=5):
    result = []
    for m in movies:
        genres_list = [g.strip() for g in str(m['Genres_normalized']).split(', ')]
        if genre in genres_list:
            result.append(m)
    random.shuffle(result)
    return result[:n]


def find_by_genres(genres, n=5):
    """Поиск фильмов, у которых есть хотя бы один из перечисленных жанров."""
    result = []
    for m in movies:
        movie_genres = [g.strip() for g in str(m['Genres_normalized']).split(', ')]
        if any(g in movie_genres for g in genres):
            result.append(m)
    random.shuffle(result)
    return result[:n]


def find_by_country(country, n=5):
    result = []
    for m in movies:
        if country.lower() in str(m['country']).lower():
            result.append(m)
    random.shuffle(result)
    return result[:n]


def find_by_year_range(year_range, n=5):
    result = []
    for m in movies:
        if m['year'] and year_range['start'] <= m['year'] <= year_range['end']:
            result.append(m)
    random.shuffle(result)
    return result[:n]


def find_by_rating(min_rating, n=5):
    result = []
    for m in movies:
            rating = float(m['rating_ball']) if m['rating_ball'] else 0
            if rating >= min_rating:
                result.append(m)
    random.shuffle(result)
    return result[:n]


def get_random_movies(n):
    return random.sample(movies, n)


def get_movie_poster(movie):
    poster_url = movie.get('url_logo', '')
    if poster_url:
        poster_url = poster_url.strip("'").strip('"')
    return poster_url


def format_movie_caption(movie):
    return f"🎬 *{movie['movie']}* ({movie['year']})\n🎭 Жанр: {movie['Genres_normalized']}\n\n📝 Описание:\n{movie['overview']}\n"


def main_keyboard():
    buttons = [
        [KeyboardButton(text="🎭 Подобрать по настроению")],
        [KeyboardButton(text="🎞️ Поиск по жанру")],
        [KeyboardButton(text="🗓️ Поиск по десятилетию")],
        [KeyboardButton(text="🌏 Поиск по стране")],
        [KeyboardButton(text="⭐ Поиск по рейтингу")],
        [KeyboardButton(text="🧩 Комбинированный поиск")],
        [KeyboardButton(text="🎲 Случайные фильмы")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True
    )


def mood_fallback_keyboard():
    """Клавиатура с готовыми вариантами настроения (если текст не распознан)."""
    buttons = []
    row = []
    for key, data in EMOTION_GENRES.items():
        row.append(InlineKeyboardButton(text=data["label"], callback_data=f"mood_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="Назад в меню", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def genres_keyboard():
    buttons = []
    row = []
    for i, genre in enumerate(get_all_genres()):
        row.append(InlineKeyboardButton(text=genre, callback_data=f"genre_{genre}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="Назад в меню", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def year_ranges_keyboard():
    buttons = []
    for yr in YEAR_RANGES:
        buttons.append([InlineKeyboardButton(text=yr["name"], callback_data=f"year_{yr['name']}")])
    buttons.append([InlineKeyboardButton(text="Назад в меню", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def countries_keyboard():
    buttons = []
    row = []
    for i, country in enumerate(get_all_countries()):
        row.append(InlineKeyboardButton(text=country, callback_data=f"country_{country}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="Назад в меню", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def ratings_keyboard():
    buttons = [
        [InlineKeyboardButton(text="⭐ 7.0 и выше", callback_data="rating_7.0")],
        [InlineKeyboardButton(text="⭐ 8.0 и выше", callback_data="rating_8.0")],
        [InlineKeyboardButton(text="⭐ 9.0 и выше", callback_data="rating_9.0")],
        [InlineKeyboardButton(text="Назад в меню", callback_data="back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_combo_genres_keyboard():
    buttons = []
    row = []
    for i, genre in enumerate(get_all_genres()):
        row.append(InlineKeyboardButton(text=genre, callback_data=f"combo_genre_{genre}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="Пропустить", callback_data="combo_genre_skip")])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="combo_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_combo_years_keyboard(genre):
    available_years = get_available_years_for_genre(genre)
    buttons = []
    row = []
    for year in available_years:
        decade_name = get_decade_name(year)
        row.append(InlineKeyboardButton(text=decade_name, callback_data=f"combo_year_{year}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="Пропустить", callback_data="combo_year_skip")])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="combo_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_combo_countries_keyboard(genre, year_range):
    available_countries = get_available_countries_for_filters(genre, year_range)
    buttons = []
    row = []
    for country in available_countries:
        row.append(InlineKeyboardButton(text=country[:20], callback_data=f"combo_country_{country}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="Пропустить", callback_data="combo_country_skip")])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="combo_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_movie(message, movie):
    if not movie:
        await message.answer("Фильм не найден", reply_markup=main_keyboard())
        return
    caption = format_movie_caption(movie)
    poster_url = get_movie_poster(movie)
    if poster_url and poster_url.startswith('http'):
        await message.answer_photo(photo=poster_url, caption=caption, parse_mode="Markdown", reply_markup=main_keyboard())
    else:
        await message.answer(caption, parse_mode="Markdown", reply_markup=main_keyboard())


async def send_mood_results(message_or_callback_message, genres, label):
    movies_found = find_by_genres(genres, 5)
    if not movies_found:
        await message_or_callback_message.answer(
            "Не нашел подходящих фильмов 😔", reply_markup=main_keyboard()
        )
        return

    await message_or_callback_message.answer(f"Похоже, тебе хочется {label} 🎬 Вот, что нашлось:")
    await send_movie(message_or_callback_message, movies_found[0])
    if len(movies_found) > 1:
        additional = "\n".join(
            f"{i + 1}. {m['movie']} ({m['year']})" for i, m in enumerate(movies_found[1:], 1)
        )
        await message_or_callback_message.answer(
            f"Ещё варианты:\n{additional}", reply_markup=main_keyboard()
        )


BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=MemoryStorage())


@dp.message(Command("start"))
async def send_welcome(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"🍿 Привет! Я бот, который поможет найти фильм для просмотра 🍿\n\n"
        f"В моей базе топ-250 фильмов по версии Кинопоиска\n\n"
        f"Что я умею:\n"
        f"- Подбирать фильм по настроению 🎭 (просто напиши, что хочешь почувствовать)\n"
        f"- Искать по жанру 🎞️\n"
        f"- Искать по десятилетию 🗓️\n"
        f"- Искать по стране 🌎\n"
        f"- Искать по рейтингу ⭐️\n"
        f"- Комбинированный поиск 🧩\n"
        f"- Случайные фильмы 🎲\n\n"
        f"Выбирай параметры 👇",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "Просто нажми на кнопку в меню!\n\n"
        "/start - перезапустить бота\n"
        "/help - справка",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


@dp.message(F.text == "🎞️ Поиск по жанру")
async def genre_search(message: Message):
    await message.answer("Выбери жанр:", parse_mode="Markdown", reply_markup=genres_keyboard())


@dp.message(F.text == "🗓️ Поиск по десятилетию")
async def year_search(message: Message):
    await message.answer("Выбери десятилетие:", parse_mode="Markdown", reply_markup=year_ranges_keyboard())


@dp.message(F.text == "🌏 Поиск по стране")
async def country_search(message: Message):
    await message.answer("Выбери страну:", parse_mode="Markdown", reply_markup=countries_keyboard())


@dp.message(F.text == "⭐ Поиск по рейтингу")
async def rating_search(message: Message):
    await message.answer("Выбери рейтинг:", parse_mode="Markdown", reply_markup=ratings_keyboard())


@dp.message(F.text == "🎲 Случайные фильмы")
async def random_movies_handler(message: Message):
    random_movies = get_random_movies(3)
    if random_movies:
        await send_movie(message, random_movies[0])


@dp.message(F.text == "🎭 Подобрать по настроению")
async def mood_search_start(message: Message, state: FSMContext):
    await state.set_state(EmotionSearch.waiting_text)
    await message.answer(
        "Расскажи, какое у тебя сейчас настроение или что ты хочешь "
        "почувствовать от фильма.\n\n"
        "Например: «хочется поплакать», «хочу что-нибудь страшное», "
        "«нужна романтика», «хочу вдохновиться», «хочу в другой мир»...",
        reply_markup=cancel_keyboard()
    )


@dp.message(EmotionSearch.waiting_text, F.text == "Отмена")
async def mood_search_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Хорошо, возвращаемся в меню", reply_markup=main_keyboard())


@dp.message(EmotionSearch.waiting_text)
async def mood_search_process(message: Message, state: FSMContext):
    result = analyze_emotion(message.text)
    if result is None:
        await message.answer(
            "Хм, не получилось понять настроение по этим словам 🤔\n"
            "Попробуй описать иначе или выбери из готовых вариантов:",
            reply_markup=mood_fallback_keyboard()
        )
        return
    emotion_key, genres, label = result
    await state.clear()
    await send_mood_results(message, genres, label)

@dp.message(F.text == "🧩 Комбинированный поиск")
async def combo_search_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Комбинированный поиск\n\n"
        "Шаг 1: Выбери жанр или нажми 'Пропустить'",
        parse_mode="Markdown",
        reply_markup=get_combo_genres_keyboard()
    )
    await state.set_state(ComboSearch.waiting_genre)


@dp.callback_query(lambda c: c.data.startswith("combo_genre_"), ComboSearch.waiting_genre)
async def combo_process_genre(callback: CallbackQuery, state: FSMContext):
    genre_data = callback.data.replace("combo_genre_", "")
    if genre_data == "skip":
        selected_genre = None
        await callback.message.edit_text(
            "Жанр пропущен\n\nШаг 2: Выбери десятилетие или нажми 'Пропустить'",
            parse_mode="Markdown",
            reply_markup=get_combo_years_keyboard(None)
        )
    else:
        selected_genre = genre_data
        await callback.message.edit_text(
            f"Выбран жанр: {selected_genre}\n\nШаг 2: Выбери десятилетие или нажми 'Пропустить'",
            parse_mode="Markdown",
            reply_markup=get_combo_years_keyboard(selected_genre)
        )
    await state.update_data(genre=selected_genre)
    await state.set_state(ComboSearch.waiting_year)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("combo_year_"), ComboSearch.waiting_year)
async def combo_process_year(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    genre = data.get("genre")
    year_data = callback.data.replace("combo_year_", "")
    if year_data == "skip":
        selected_year = None
        await callback.message.edit_text(
            "Десятилетие пропущено\n\nШаг 3: Выбери страну или нажми 'Пропустить'",
            parse_mode="Markdown",
            reply_markup=get_combo_countries_keyboard(genre, None)
        )
    else:
        decade_start = int(year_data)
        selected_year = {"name": f"{decade_start}-{decade_start+9}", "start": decade_start, "end": decade_start+9}
        await callback.message.edit_text(
            f"Выбрано десятилетие: {selected_year['name']}\n\nШаг 3: Выбери страну или нажми 'Пропустить'",
            parse_mode="Markdown",
            reply_markup=get_combo_countries_keyboard(genre, selected_year)
        )
    await state.update_data(year_range=selected_year)
    await state.set_state(ComboSearch.waiting_country)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("combo_country_"), ComboSearch.waiting_country)
async def combo_process_country(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    genre = data.get("genre")
    year_range = data.get("year_range")
    country_data = callback.data.replace("combo_country_", "")
    if country_data == "skip":
        selected_country = None
    else:
        selected_country = country_data
    results = get_filtered_movies(genre, year_range, selected_country, 5)
    await callback.message.delete()
    if results:
        movie = results[0]
        caption = format_movie_caption(movie)
        poster_url = get_movie_poster(movie)
        if poster_url and poster_url.startswith('http'):
            await callback.message.answer_photo(photo=poster_url, caption=caption, parse_mode="Markdown", reply_markup=main_keyboard())
        else:
            await callback.message.answer(caption, parse_mode="Markdown", reply_markup=main_keyboard())
        if len(results) > 1:
            additional = "\n".join([f"{i+1}. {m['movie']} ({m['year']})" for i, m in enumerate(results[1:], 1)])
            await callback.message.answer(
                f"Ещё фильмы:\n{additional}",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
    else:
        await callback.message.answer("Фильмы не найдены", parse_mode="Markdown", reply_markup=main_keyboard())
    await state.clear()
    await callback.answer()


@dp.callback_query(lambda c: c.data == "combo_cancel")
async def combo_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "Поиск отменён",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("genre_"))
async def handle_genre(callback: CallbackQuery):
    genre = callback.data.replace("genre_", "")
    result = find_by_genre(genre, 1)
    await callback.message.delete()
    if result:
        await send_movie(callback.message, result[0])
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("year_"))
async def handle_year(callback: CallbackQuery):
    year_name = callback.data.replace("year_", "")
    year_range = None
    for yr in YEAR_RANGES:
        if yr["name"] == year_name:
            year_range = yr
            break
    if year_range:
        result = find_by_year_range(year_range, 1)
        await callback.message.delete()
        if result:
            await send_movie(callback.message, result[0])
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("country_"))
async def handle_country(callback: CallbackQuery):
    country = callback.data.replace("country_", "")
    result = find_by_country(country, 1)
    await callback.message.delete()
    if result:
        await send_movie(callback.message, result[0])
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("rating_"))
async def handle_rating(callback: CallbackQuery):
    rating = float(callback.data.replace("rating_", ""))
    result = find_by_rating(rating, 1)
    await callback.message.delete()
    if result:
        await send_movie(callback.message, result[0])
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("mood_"))
async def handle_mood_fallback(callback: CallbackQuery, state: FSMContext):
    emotion_key = callback.data.replace("mood_", "")
    data = EMOTION_GENRES.get(emotion_key)
    await callback.message.delete()
    await state.clear()
    if data:
        await send_mood_results(callback.message, data["genres"], data["label"])
    await callback.answer()


@dp.callback_query(lambda c: c.data == "back")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "Главное меню\n\nВыбери действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    await callback.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
