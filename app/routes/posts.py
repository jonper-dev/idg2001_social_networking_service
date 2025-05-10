from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.db import get_db
from app import crud
from app.models.models import Post, PostCreate, PostUpdate, PostPatch, PostOutput
from app.session import get_user_id as lookup_user_id, session_store


router = APIRouter(prefix="/posts", tags=["posts"])

#########################
### -- GET-methods -- ###
#########################
## Finding current user if applicable for posts
def get_current_user_id(session_id: str = Cookie(None)) -> int:
    if not session_id:
        raise HTTPException(status_code=401, detail="Not logged in.")
    user_id = lookup_user_id(session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user_id

## Finding current user without requiring login.
def get_optional_user_id(session_id: str = Cookie(None)) -> Optional[int]:
    if not session_id:
        return None
    return lookup_user_id(session_id)

## Getting all posts (and comment-posts), also used for showing posts.
@router.get("/", response_model=List[PostOutput])
def get_posts(
    db: Session = Depends(get_db),
    user_id: Optional[int] = Depends(get_optional_user_id)
):
    posts = db.query(Post).options(joinedload(Post.likes), joinedload(Post.author)).all()

    return [
        PostOutput(
            id=post.id,
            content=post.content,
            timestamp=post.created_at,
            user_id=post.user_id,
            username=post.author.name,
            likes=len(post.likes),
            is_liked_by_user=any(liker.id == user_id for liker in post.likes) if user_id else False
        )
        for post in posts
    ]


## Getting a specific post by its ID.
@router.get("/{post_id}")
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    return post

## Search posts by content
@router.get("/search")
def search(
    query: str,
    type: str = "posts",  # Default to searching posts
    db: Session = Depends(get_db)
):
    if type == "posts":
        results = crud.search_posts(db, query)
    elif type == "accounts":
        results = crud.search_accounts(db, query)
    elif type == "hashtags":
        results = crud.search_hashtags(db, query)
    else:
        raise HTTPException(status_code=400, detail="Invalid search type.")
    
    return results


###########################
### -- Other methods -- ###
###########################

## Helper function for veryfying posts
def verify_ownership(post, user_id):
    if post.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized.")

## Creating a new post (or comment-post). A new post-ID will be assigned.
@router.post("/")
def create_post(post_data: PostCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_post(db, post_data)
    except Exception as e:
        print("Error creating post:", e)
        raise HTTPException(status_code=500, detail="Could not create post.")

## Updating a post.
@router.put("/{post_id}")
def update_post(post_id: int, updated: PostUpdate, request: Request, db: Session = Depends(get_db)):
    user_id = check_user_authenticated(request)
    post = crud.get_post(db, post_id, updated.content)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    ## Verify ownership using helper function 
    verify_ownership(post, user_id)
    return crud.update_post(db, post_id, updated.content)

## Partial update of a post. Only the fields that are provided will be updated.
@router.patch("/{post_id}")
def partial_update_post(post_id: int, post_update: PostPatch, request: Request, db: Session = Depends(get_db)):
    user_id = check_user_authenticated(request)
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    
    ## Verify ownership helper function
    verify_ownership(post, user_id)
    if post_update.content is not None:
        post.content = post_update.content
        db.commit()
        db.refresh(post)

    return post

## Delete post
@router.delete("/{post_id}")
def delete_post(post_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = check_user_authenticated(request)
    post = crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    
    verify_ownership(post, user_id)
    crud.delete_post(db, post_id)
    return {"message": "Post deleted."}

##########################
### Like / Unlike Post ###
##########################
def check_user_authenticated(request: Request):
    ### Helper function to check if the user is authenticated using the session.
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in session_store:
        raise HTTPException(status_code=401, detail="User not authenticated")
    return get_current_user_id(session_id)

## Like post
@router.post("/{post_id}/like")
def like_post(post_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return crud.toggle_like(db, user_id, post_id)

# @router.post("/like/{post_id}")
# def like_post(post_id: int, request: Request, db: Session = Depends(get_db)):
#     user_id = check_user_authenticated(request)  # Use the helper function

#     post = crud.get_post(db, post_id)
#     if not post:
#         raise HTTPException(status_code=404, detail="Post not found")

#     if crud.is_post_liked_by_user(db, post_id, user_id):
#         raise HTTPException(status_code=400, detail="Already liked this post")

#     crud.like_post(db, user_id, post_id)

#     return JSONResponse(content={"message": "Post liked successfully"}, status_code=200)

## Unlike Post
@router.post("/{post_id}/unlike")
def unlike_post(post_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = check_user_authenticated(request)  # Use the helper function

    post = crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")

    if not crud.is_post_liked_by_user(db, post_id, user_id):
        raise HTTPException(status_code=400, detail="Post not liked yet.")

    crud.unlike_post(db, user_id, post_id)

    return JSONResponse(content={"message": "Post unliked successfully."}, status_code=200)

