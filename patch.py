with open("backend/app/auth.py", "r") as f:
    content = f.read()

new_code = """    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid token header")

    crit = header.get('crit')
    if crit is not None:
        understood = {'typ', 'alg', 'cty', 'kid'}
        for crit_header in crit:
            if crit_header not in understood:
                raise HTTPException(status_code=401, detail="critical header not understood")

    header_alg = _validate_jwt_header(header)"""

content = content.replace("""    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid token header")

    header_alg = _validate_jwt_header(header)""", new_code)

new_code2 = """                "verify_aud": bool(settings.oidc_audience),
                "verify_iss": True,
                "verify_exp": True,
                "require": ["exp", "iss", "jti"] + (["aud"] if bool(settings.oidc_audience) else []),"""

content = content.replace("""                "verify_aud": bool(settings.oidc_audience),
                "verify_iss": True,
                "verify_exp": True,
                "verify_jti": True,
                "require": ["exp", "iss", "jti"] + (["aud"] if bool(settings.oidc_audience) else []),""", new_code2)

with open("backend/app/auth.py", "w") as f:
    f.write(content)
