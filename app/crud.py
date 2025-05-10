from sqlalchemy.orm import Session, joinedload
from app.models.models import User, Post, Hashtag, likes_table as likes, post_hashtags
from sqlalchemy import or_
import bcrypt
import logging

logger = logging.getLogger(__name__)

######################
### -- PASSWORD -- ###
######################
## Password hashing
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

## Password verification
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


###################
### -- USERS -- ###
###################
## Login
def get_users(db: Session):
    return db.query(User).all()

def get_user(db: Session, user_id: int):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"User with ID {user_id} not found.")
    return user

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def verify_user_credentials(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if user and verify_password(password, user.password):  # Use the verify_password function
        return user
    return None

## Signup
def create_user(db: Session, name: str, email: str, password: str):
    hashed_pw = hash_password(password)
    user = User(name=name, email=email, password=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

## Update user
def update_user(db: Session, user_id: int, name: str, email: str, password: str):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    user.name = name
    user.email = email
    user.password = hash_password(password)  # Ensure password is hashed
    db.commit()
    db.refresh(user)
    return user

## Partial update user
def partial_update_user(db: Session, user_id: int, updates: dict):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    for key, value in updates.items():
        if key == "password":  # Ensure password is hashed
            value = hash_password(value)
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

def follow_user(db: Session, follower_id: int, followed_id: int):
    follower = db.query(User).get(follower_id)
    followed = db.query(User).get(followed_id)
    if not follower or not followed:
        return None  # Return None if either user does not exist
    if followed not in follower.following:
        follower.following.append(followed)
        db.commit()
    return follower

## List all accounts
def list_accounts(db: Session, skip: int = 0, limit: int = 100):
    return db.query(User).offset(skip).limit(limit).all()


###################
### -- POSTS -- ###
###################
def create_post(db: Session, post_data):
    from app.models.models import Post, Hashtag  # Avoid circular imports

    if not post_data.content or not post_data.user_id:
        raise ValueError("Post content and user_id are required.")  # Validate input

    post = Post(
        content=post_data.content,
        user_id=post_data.user_id,
        reply_to_id=post_data.reply_to_id
    )

    # Handle hashtags
    for tag in post_data.hashtags:
        tag = tag.lower().strip()
        existing = db.query(Hashtag).filter(Hashtag.name == tag).first()
        if existing:
            post.hashtags.append(existing)
        else:
            new_tag = Hashtag(name=tag)
            db.add(new_tag)
            post.hashtags.append(new_tag)

    db.add(post)
    db.commit()
    db.refresh(post)
    return post

## Get all posts (includes user table [author here] for joined table-operations)
def get_posts(db: Session):
    return db.query(Post).options(joinedload(Post.author)).all()

## Get post by ID
def get_post(db: Session, post_id: int):
    return db.query(Post).filter(Post.id == post_id).first()

## Update post
def update_post(db: Session, post_id: int, content: str):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return None
    post.content = content
    post.edited = True
    db.commit()
    db.refresh(post)
    return post

## Partial update post
def partial_update_post(db: Session, post_id: int, updates: dict):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return None
    for key, value in updates.items():
        setattr(post, key, value)
    db.commit()
    db.refresh(post)
    return post

## Delete post
def delete_post(db: Session, post_id: int):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return None
    db.delete(post)
    db.commit()
    return post

## Likes for posts
def toggle_like(db: Session, user_id: int, post_id: int):
    user = db.query(User).get(user_id)
    post = db.query(Post).get(post_id)

    if not user or not post:
        return None

    if user in post.likes:
        post.likes.remove(user)
        liked = False
    else:
        post.likes.append(user)
        liked = True

    db.commit()
    return {"liked": liked, "likes": len(post.likes)}

def like_post(db: Session, user_id: int, post_id: int):
    # Insert a like into the likes table
    new_like = likes.insert().values(user_id=user_id, post_id=post_id)
    db.execute(new_like)
    db.commit()

def unlike_post(db: Session, user_id: int, post_id: int):
    # Remove the like from the likes table
    db.execute(likes.delete().where(likes.c.user_id == user_id).where(likes.c.post_id == post_id))
    db.commit()

def is_post_liked_by_user(db: Session, post_id: int, user_id: int):
    # Check if the user has already liked the post
    result = db.execute(likes.select().where(likes.c.user_id == user_id).where(likes.c.post_id == post_id)).fetchone()
    return result is not None

## Reply to post
def reply_to_post(db: Session, user_id: int, content: str, parent_id: int):
    return create_post(db, post_data={"user_id": user_id, "content": content, "reply_to_id": parent_id})

####################
### -- SEARCH -- ###
####################
## SignupSearch posts
def search_posts(db: Session, query: str):
    return db.query(Post).filter(
        or_(
            Post.content.ilike(f"%{query}%"),
            Post.hashtags.any(Hashtag.name.ilike(f"%{query}%"))
        )
    ).all()

## Search for accounts
def search_accounts(db: Session, query: str):
    return db.query(User).filter(
        or_(
            User.name.ilike(f"%{query}%"),
            User.email.ilike(f"%{query}%")
        )
    ).all()

## Search hashtags
def search_hashtags(db: Session, tag: str):
    return db.query(Hashtag).filter(Hashtag.name.ilike(f"%{tag}%")).all()
