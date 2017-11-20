drop table if exists add_request;
create table add_request (
  id integer primary key autoincrement,
  username text not null,
  imdb_id text not null,
  seasons text
);

drop table if exists user;
create table user (
  id integer primary key autoincrement,
  username text not null,
  password text not null,
  auth_token text
);

drop table if exists episode;
create table episode (
  title_imdb_id text not null,
  episode_title text not null,
  episode_denormalized text not null
)